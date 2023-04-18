import discord
import math
import os
import random
import traceback
from dotenv import load_dotenv

# importing other classes from other files
import Utils
from Pages import Pages
from Player import Player
from Servers import Servers
from Song import Song
from YTDLInterface import YTDLInterface

# needed to add it to a var bc of pylint on my laptop but i delete it right after
XX = '''
#-fnt stands for finished not tested
#-f is just finished
TODO:
    9- figure out what broke now that player can be silent for long periods while the queue is empty (like skip being able to run while queue is empty)
    8- make play and playlist only join VC if the provided queries are valid (prevents bot from joining to just do nothing)
    8-fnt make forceskip admin-only
    6-fnt alert user when songs were unable to be added inside _playlist()
    -make more commands
        3- merge play and playlist
        1- create add-at(?) (merge with playtop? ask for int instead of bool?)
        1- help #bear //done but needs to be updated
        1- settings #bear
        1- option to decide if __send_np goes into vc.channel or song.channel
        1- remove author's songs from queue when author leaves vc #sming //can't be done until we have settings
        1- move command #bear 
    -other
        8- perform link saniti*zation before being sent to yt-dlp
        7- only generate a player when audio is playing, remove the player_event, force initialization with a Song or Queue
        5- rename get_embed's content argument to description
        5- access currently playing song via player.song rather than player.queue.top() (maybe remove current song from queue while we're at it?)
        ^^^ player.queue.top() is not always == player.song, player.queue.top() exists before player.song is uninitialized, make this swap with care
        ^^^ it's likely fine but still, race conditions.
        


DONE:
    9-f make listener for player.start returning to call clean() // found alternative that probably works better
    9-f fix automatic now_playing messages
    8-f make YTDLInterface.query_link calls cognizant of entries[] and able to handle it's appearance
    8-f likewise, make query_search able to handle a lack of entries[] // Never going to happen; (hopefully) a non issue
    7-fnt create general on_error event method
     - make more commands
        9-f pause #bear //vc.pause() and vc.resume()
        9-f resume #bear
        9-f now #bear
        9-f skip (force skip) #sming
        8-f search #sming
        8-f queue #bear
        8-f remove #bear
        8-f play_top #bear
        7-f remove user's songs from queue
        7-f play_list #sming
        7-f play_list_shuffle #sming
        6-f clear #bear
        5-f shuffle #bear
        4-f loop (queue, song) #bear
     - Be able to play music from youtube
        - play music
        - stop music
    (kind but found a better way)- get downloading to work
     - Be able to join vc and play sound
        - join vc
        - leave vc
        - play sound
    - other
        9-f footer that states the progress of the song #bear
        8-f fix auto now playing messages not deleting //found why, it's because the player.wait_until_termination() returns instantly once we tell the player to close
        8-f auto-leave VC if bot is alone #sming
        4-f remove unneeded async defs
        3-f make it multi server #bear

'''
del XX

load_dotenv()  # getting the key from the .env file
key = os.environ.get('key')


class Bot(discord.Client):  # initiates the bots intents and on_ready event
    def __init__(self):
        intents = discord.Intents.default()
        intents.members = True
        intents.message_content = True
        super().__init__(intents=intents)

    async def on_ready(self):
        await tree.sync()  # please dont remove just in case i need to sync
        Utils.pront("Bot is ready", lvl="OKGREEN")
        await self.change_presence(activity=discord.Activity(
            type=discord.ActivityType.watching, name=f"you in {len(bot.guilds):,} Servers."))


# Global Variables
bot = Bot()
tree = discord.app_commands.CommandTree(bot)


## EVENT LISTENERS ##


@bot.event
async def on_voice_state_update(member: discord.Member, before: discord.VoiceState, after: discord.VoiceState) -> None:
    # If we don't care that a voice state was updated
    if member.guild.voice_client is None:
        return

    # If the user was in the same VC as the bot
    if before.channel == member.guild.voice_client.channel:
        # If the bot is now alone
        if len(before.channel.members) == 1:
            player = Servers.get_player(member.guild.id)
            if player is None:
                member.guild.voice_client.disconnect()
            else:
                await Utils.clean(player)


# Error handler
@bot.event
async def on_error(interaction, error):
    # Send generic error string
    await Utils.send(interaction, "MaBalls ran into a problem.", error)
    raise error

## COMMANDS ##


@ tree.command(name="ping", description="The ping command (^-^)")
async def _ping(interaction: discord.Interaction) -> None:
    # await send(interaction, title='Pong!', content=':ping_pong:')
    await interaction.response.send_message('Pong!', ephemeral=True)


@ tree.command(name="join", description="Adds the MaBalls to the voice channel you are in")
async def _join(interaction: discord.Interaction) -> None:
    if interaction.user.voice is None:
        await interaction.response.send_message('You are not in a voice channel', ephemeral=True)
        return
    if interaction.guild.voice_client is not None:
        await interaction.response.send_message('I am already in a voice channel', ephemeral=True)
        return
    # Connect to the voice channel
    await interaction.user.voice.channel.connect(self_deaf=True)
    await Utils.send(interaction, title='Joined!', content=':white_check_mark:', progress=False)


@ tree.command(name="leave", description="Removes the MaBalls from the voice channel you are in")
async def _leave(interaction: discord.Interaction) -> None:
    if not await Utils.Pretests.voice_channel(interaction):
        return

    # Disconnect from the voice channel
    await Utils.clean(interaction.guild_id)
    await Utils.send(interaction, title='Left!', content=':white_check_mark:', progress=False)


@ tree.command(name="play", description="Plays a song from youtube(or other sources somtimes) in the voice channel you are in")
async def _play(interaction: discord.Interaction, link: str, top: bool = False) -> None:
    # Check if author is in VC
    if interaction.user.voice is None:
        await interaction.response.send_message('You are not in a voice channel', ephemeral=True)
        return
    
    # Check if author is in the *right* vc if it applies
    if interaction.guild.voice_client is not None and interaction.user.voice.channel != interaction.guild.voice_client.channel:
        await interaction.response.send_message("You must be in the same voice channel in order to use MaBalls", ephemeral=True)
        return

    await interaction.response.defer(thinking=True)

    song = await Song.from_link(interaction, link)
    # Check if song.populated didnt fail (duration is just a random attribute to check)
    if song.duration is None:
        await interaction.followup.send(embed=Utils.get_embed(interaction, title='Error!', content='Invalid link', progress=False), ephemeral=True)
        return
    
    # If not in a VC
    if interaction.guild.voice_client is None:
        channel = interaction.user.voice.channel
        vc = await channel.connect(self_deaf=True)
        Servers.add(interaction.guild_id, Player(vc, song))
    else:
        # If we already are it means a Queue already exists, so add the song to it
        if top:
            Servers.get_player(interaction.guild_id).queue.add_at(song, 1)
        else:
            Servers.get_player(interaction.guild_id).queue.add(song)


    embed = Utils.get_embed(
        interaction,
        title='Added to Queue:',
        url=song.original_url,
        color=Utils.get_random_hex(song.id)
    )
    embed.add_field(name=song.uploader, value=song.title, inline=False)
    embed.add_field(name='Requested by:', value=song.requester.mention)
    embed.add_field(name='Duration:', value=Song.parse_duration(song.duration))
    embed.set_thumbnail(url=song.thumbnail)
    await interaction.followup.send(embed=embed)


@ tree.command(name="skip", description="Skips the currently playing song")
async def _skip(interaction: discord.Interaction) -> None:
    if not await Utils.Pretests.playing_audio(interaction):
        return

    player = Servers.get_player(interaction.guild_id)

    # Get a complex embed for votes
    async def skip_msg(title: str = '', content: str = '', present_tense: bool = True, ephemeral: bool = False) -> None:

        embed = Utils.get_embed(interaction, title, content,
                                color=Utils.get_random_hex(player.song.id),
                                progress=present_tense)
        embed.set_thumbnail(url=player.song.thumbnail)

        users = ''
        for user in player.song.vote.get():
            users = f'{user.name}, {users}'
        users = users[:-2]
        if present_tense:
            # != 1 because if for whatever reason len(skip_vote) == 0 it will still make sense
            voter_message = f"User{'s who have' if len(player.song.vote) != 1 else ' who has'} voted to skip:"
            song_message = "Song being voted on:"
        else:
            voter_message = f"Vote passed by:"
            song_message = "Song that was voted on:"

        embed.add_field(name="Initiated by:",
                        value=player.song.vote.initiator.mention)
        embed.add_field(name=song_message,
                        value=player.song.title, inline=True)
        embed.add_field(name=voter_message, value=users, inline=False)
        await interaction.response.send_message(embed=embed, ephemeral=ephemeral)

    # If there's not enough people for it to make sense to call a vote in the first place
    if len(player.vc.channel.members) <= 3:
        player.vc.stop()
        await Utils.send(interaction, "Skipped!", ":white_check_mark:")
        return

    votes_required = len(player.vc.channel.members) // 2

    if player.song.vote is None:
        # Create new Vote
        player.song.create_vote(interaction.user)
        await skip_msg("Vote added.", f"{votes_required - len(player.song.vote)}/{votes_required} votes to skip.")
        return

    # If user has already voted to skip
    if interaction.user in player.song.vote.get():
        await skip_msg("You have already voted to skip!", ":octagonal_sign:", ephemeral=True)
        return

    # Add vote
    player.song.vote.add(interaction.user)

    # If vote succeeds
    if len(player.song.vote) >= votes_required:
        await skip_msg("Skip vote succeeded! :tada:", present_tense=False)
        player.song.vote = None
        player.vc.stop()
        return

    await skip_msg("Vote added.", f"{votes_required - len(player.song.vote)}/{votes_required} votes to skip.")


@ tree.command(name="forceskip", description="Skips the currently playing song without having a vote. (Requires Manage Channels permission.)")
async def _force_skip(interaction: discord.Interaction) -> None:
    if not await Utils.Pretests.playing_audio(interaction):
        return

    # If user doesn't have the permissions
    if not interaction.user.guild_permissions.manage_channels:
        # If there's enough users in vc for it to make sense to enforce the perms
        if len(Servers.get_player(interaction.guild.id).vc.channel.members) > 3:
            await Utils.send(interaction, "Insufficient Permissions!", 'This command requires the "Manage Channels" permission!', ephemeral=True)
            return

    Servers.get_player(interaction.guild_id).vc.stop()
    await Utils.send(interaction, "Skipped!", ":white_check_mark:")


@ tree.command(name="queue", description="Shows the current queue")
async def _queue(interaction: discord.Interaction, page: int = 1) -> None:
    if not await Utils.Pretests.voice_channel(interaction):
        return
    # Convert page into non-user friendly (woah scary it starts at 0)(if only we were using lua)
    page -= 1
    player = Servers.get_player(interaction.guild_id)
    if not player.queue.get():
        await Utils.send(interaction, title='Queue is empty!', ephemeral=True)
        return
    embed = Utils.get_embed(interaction, title='Queue', color=Utils.get_random_hex(
        player.queue.top().id), progress=False)
    page_size = 5
    queue_len = len(player.queue)
    min_queue_index = page_size * (page - 1)
    max_queue_index = min_queue_index + page_size
    max_page = math.ceil(queue_len / page_size)
    # check for highest page
    if max_page < page or page < 0:
        await interaction.response.send_message(
            "Page doesn't exist! :octagonal_sign:", ephemeral=True)
        return
    # The index to start reading from Queue
    min_queue_index = page_size * (page)
    # The index to stop reading from Queue
    max_queue_index = min_queue_index + page_size

    embed = Utils.get_embed(interaction, title='Queue', color=Utils.get_random_hex(
        player.song.id), progress=False)

    # Loop through the region of songs in this page
    for i in range(min_queue_index, max_queue_index):
        if i >= queue_len:
            break
        song = player.queue.get()[i]

        embed.add_field(name=f"`{i }`: {song.title}",
                        value=f"by {song.uploader}\nAdded By: {song.requester.mention}", inline=False)

    embed.set_footer(
        text=f"Page {page + 1}/{max_page} | {queue_len} song{'s' if queue_len != 1 else ''} in queue")

    await interaction.response.send_message(embed=embed)


@ tree.command(name="now", description="Shows the current song")
async def _now(interaction: discord.Interaction) -> None:
    if not await Utils.Pretests.player_exists(interaction):
        return
    if (Servers.get_player(interaction.guild_id).song is None):
        await Utils.send(interaction, title="Nothing is playing", content="You should add something")
        return
    await interaction.response.send_message(embed=Utils.get_now_playing_embed(Servers.get_player(interaction.guild_id), progress=True))


@ tree.command(name="remove", description="Removes a song from the queue")
async def _remove(interaction: discord.Interaction, number_in_queue: int) -> None:
    if not await Utils.Pretests.player_exists(interaction):
        return
    removed_song = Servers.get_player(
        interaction.guild_id).queue.remove(number_in_queue + 1)
    if removed_song is not None:
        embed = discord.Embed(
            title='Removed from Queue:',
            url=removed_song.original_url,
            color=Utils.get_random_hex(removed_song.id)
        )
        embed.add_field(name=removed_song.uploader,
                        value=removed_song.title, inline=False)
        embed.add_field(name='Requested by:',
                        value=removed_song.requester.mention)
        embed.add_field(name='Duration:',
                        value=Song.parse_duration(removed_song.duration))
        embed.set_thumbnail(url=removed_song.thumbnail)
        embed.set_author(name=removed_song.requester.display_name,
                         icon_url=removed_song.requester.display_avatar.url)
        await interaction.response.send_message(embed=embed)


@ tree.command(name="removeuser", description="Removes all of the songs added by a specific user")
async def _remove_user(interaction: discord.Interaction, member: discord.Member):
    if not await Utils.Pretests.player_exists(interaction):
        return

    queue = Servers.get_player(interaction.guild.id).queue

    # TODO either make this an int or fill out the send embed more
    removed = []
    i = 1
    while i < len(queue.get()):
        if queue.get(i).requester == member:
            removed.append(queue.remove(i))
            continue

        # Only increment i when song.requester != member
        i += 1

    await Utils.send(interaction,
                     title=f'Removed {len(removed)} songs.')


@ tree.command(name="playlist", description="Adds a playlist to the queue")
async def _playlist(interaction: discord.Interaction, link: str, shuffle: bool = False) -> None:
    # Check if author is in VC
    if interaction.user.voice is None:
        await interaction.response.send_message('You are not in a voice channel', ephemeral=True)
        return
    
    # Check if author is in the *right* vc if it applies
    if interaction.guild.voice_client is not None and interaction.user.voice.channel != interaction.guild.voice_client.channel:
        await interaction.response.send_message("You must be in the same voice channel in order to use MaBalls", ephemeral=True)
        return
    
    await interaction.response.defer(thinking=True)

    playlist = await YTDLInterface.query_link(link)

    if playlist.get('_type') != "playlist" or playlist.get('thumbnails') is None:
        await interaction.followup.send(embed=Utils.get_embed(interaction, "Not a playlist."), ephemeral=True)
        return

    # Shuffle the entries[] within playlist before processing them
    if shuffle:
        random.shuffle(playlist.get("entries"))

    errored_song_positions = []

    for i, entry in enumerate(playlist.get("entries")):
        # If entry didn't populate properly, take note and skip it.
        if entry.get("duration") is None:
            # Convert to human-readable count
            errored_song_positions.append(i+1)
            continue
        # Feed the Song the entire entry, saves time by not needing to create and fill a dict
        song = Song(interaction, link, entry)

        # Add song to Player, create it if it doesn't exist
        if interaction.guild.voice_client is None:
            channel = interaction.user.voice.channel
            vc = await channel.connect(self_deaf=True)
            Servers.add(interaction.guild_id, Player(vc, song))
        else:
            Servers.get_player(interaction.guild_id).queue.add(song)


    embed = Utils.get_embed(
        interaction,
        title='Added playlist to Queue:',
        # Sorry for this being a bit of a mess
        # If there were errored songs, generate a content that describes them
        content=None if len(errored_song_positions) == 0 else f'''
        The {'song at position' if len(errored_song_positions) == 1 else 'songs at positions'}
        {str(errored_song_positions)[1:-1]}
        failed to load properly, please try with a different URL.
        ''',
        url=playlist.get('original_url'),
        color=Utils.get_random_hex(playlist.get('id'))
    )
    embed.add_field(name=playlist.get('uploader'), value=playlist.get('title'))
    embed.add_field(
        name='Length:', value=f'{playlist.get("playlist_count")} songs')
    embed.add_field(name='Requested by:', value=interaction.user.mention)
    # Get the highest resolution thumbnail available
    embed.set_thumbnail(url=playlist.get('thumbnails')[-1].get('url'))

    await interaction.followup.send(embed=embed)


@ tree.command(name="search", description="Searches YouTube for a given query")
async def _search(interaction: discord.Interaction, query: str, selection: int = None) -> None:
    # Check if author is in VC
    if interaction.user.voice is None:
        await interaction.response.send_message('You are not in a voice channel', ephemeral=True)
        return
    
    # Check if author is in the *right* vc if it applies
    if interaction.guild.voice_client is not None and interaction.user.voice.channel != interaction.guild.voice_client.channel:
        await interaction.response.send_message("You must be in the same voice channel in order to use MaBalls", ephemeral=True)
        return

    await interaction.response.defer(thinking=True)

    query_result = await YTDLInterface.query_search(query)

    if selection:
        selection -= 1
        entry = query_result.get('entries')[selection]

        song = Song(interaction, entry.get('original_url'), entry)

        # Add song to Player, create it if it doesn't exist
        if interaction.guild.voice_client is None:
            channel = interaction.user.voice.channel
            vc = await channel.connect(self_deaf=True)
            Servers.add(interaction.guild_id, Player(vc, song))
        else:
            Servers.get_player(interaction.guild_id).queue.add(song)

        # Create embed to go along with it
        embed = Utils.get_embed(
            interaction,
            title='Added to Queue:',
            url=song.original_url,
            color=Utils.get_random_hex(song.id)
        )
        embed.add_field(name=song.uploader, value=song.title, inline=False)
        embed.add_field(name='Requested by:', value=song.requester.mention)
        embed.add_field(name='Duration:',
                        value=Song.parse_duration(song.duration))
        embed.set_thumbnail(url=song.thumbnail)
        await interaction.followup.send(embed=embed)
        return

    # player = Servers.get_player(interaction.guild_id)
    embeds = []
    embeds.append(Utils.get_embed(interaction,
                                  title="Search results:",
                                  ))
    for i, entry in enumerate(query_result.get('entries')):
        embed = Utils.get_embed(interaction,
                                title=f'`[{i+1}]`  {entry.get("title")} -- {entry.get("channel")}',
                                url=entry.get('webpage_url'),
                                color=Utils.get_random_hex(
                                    entry.get("id"))
                                )
        embed.add_field(name='Duration:', value=Song.parse_duration(
            entry.get('duration')), inline=True)
        embed.set_thumbnail(url=entry.get('thumbnail'))
        embeds.append(embed)

    await interaction.followup.send(embeds=embeds)


@ tree.command(name="clear", description="Clears the queue")
async def _clear(interaction: discord.Interaction) -> None:
    if not await Utils.Pretests.player_exists(interaction):
        return
    Servers.get_player(interaction.guild_id).queue.clear()
    await interaction.response.send_message('Queue cleared')


@ tree.command(name="shuffle", description="Shuffles the queue")
async def _shuffle(interaction: discord.Interaction) -> None:
    if not await Utils.Pretests.player_exists(interaction):
        return
    Servers.get_player(interaction.guild_id).queue.shuffle()
    await interaction.response.send_message('Queue shuffled')


@ tree.command(name="pause", description="Pauses the current song")
async def _pause(interaction: discord.Interaction) -> None:
    if not await Utils.Pretests.player_exists(interaction):
        return
    Servers.get_player(interaction.guild_id).vc.pause()
    Servers.get_player(interaction.guild_id).song.pause()
    await Utils.send(interaction, title='Paused')


@ tree.command(name="resume", description="Resumes the current song")
async def _resume(interaction: discord.Interaction) -> None:
    if not await Utils.Pretests.playing_audio(interaction):
        return
    Servers.get_player(interaction.guild_id).vc.resume()
    Servers.get_player(interaction.guild_id).song.resume()
    await Utils.send(interaction, title='Resumed')


@ tree.command(name="loop", description="Loops the current song")
async def _loop(interaction: discord.Interaction) -> None:
    if not await Utils.Pretests.player_exists(interaction):
        return
    player = Servers.get_player(interaction.guild.id)
    player.set_loop(not player.looping)
    await Utils.send(interaction, title='Looped.' if player.looping else 'Loop disabled.')


@ tree.command(name="queueloop", description="Loops the queue")
async def _queue_loop(interaction: discord.Interaction) -> None:
    if not await Utils.Pretests.player_exists(interaction):
        return
    player = Servers.get_player(interaction.guild.id)
    player.set_queue_loop(not player.queue_looping)
    await Utils.send(interaction, title='Queue looped.' if player.queue_looping else 'Queue loop disabled.')


@ tree.command(name="help", description="Shows the help menu")
@ discord.app_commands.describe(commands="choose a command to see more info")
@ discord.app_commands.choices(commands=[
    # discord.app_commands.Choice(name="none", value=""),
    discord.app_commands.Choice(name="ping", value="ping"),
    discord.app_commands.Choice(name="help", value="help"),
    discord.app_commands.Choice(name="join", value="join"),
    discord.app_commands.Choice(name="leave", value="leave"),
    discord.app_commands.Choice(name="play", value="play"),
    discord.app_commands.Choice(name="skip", value="skip"),
    discord.app_commands.Choice(name="forceskip", value="forceskip"),
    discord.app_commands.Choice(name="queue", value="queue"),
    discord.app_commands.Choice(name="now", value="now"),
    discord.app_commands.Choice(name="remove", value="remove"),
    discord.app_commands.Choice(name="removeuser", value="removeuser"),
    discord.app_commands.Choice(name="playlist", value="playlist"),
    discord.app_commands.Choice(name="search", value="search"),
    discord.app_commands.Choice(name="clear", value="clear"),
    discord.app_commands.Choice(name="shuffle", value="shuffle"),
    discord.app_commands.Choice(name="pause", value="pause"),
    discord.app_commands.Choice(name="resume", value="resume"),
    discord.app_commands.Choice(name="loop", value="loop"),
    discord.app_commands.Choice(name="queueloop", value="queueloop")
])
async def _help(interaction: discord.Interaction, commands: discord.app_commands.Choice[str] = "") -> None:
    if not commands:
        main_embed = Pages.main_page
        embed = Utils.get_embed(
            interaction, title=main_embed["title"], content=main_embed["description"])
        for field in main_embed["fields"]:
            embed.add_field(name=field["name"], value=field["value"])
        await interaction.response.send_message(embed=embed)
        return
    command_embed_dict = Pages.get_page(commands.value)
    embed = Utils.get_embed(
        interaction, title=command_embed_dict["title"], content=command_embed_dict["description"])
    for field in command_embed_dict["fields"]:
        embed.add_field(name=field["name"], value=field["value"])
    await interaction.response.send_message(embed=embed)

# Custom error handler


async def on_tree_error(interaction: discord.Interaction, error: discord.app_commands.AppCommandError):
    await interaction.channel.send(embed=Utils.get_embed(interaction, title="MaBalls ran into Ma issue.", content=f'```ansi\n{error}```'))
    traceback.print_exc()
tree.on_error = on_tree_error

bot.run(key)
