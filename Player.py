import asyncio
import discord
import random
from Queue import Queue
from Song import Song
from YTDLInterface import YTDLInterface


class Player:
    def __init__(self, vc: discord.VoiceClient) -> None:
        self.player_event = asyncio.Event()
        self.player_abort = asyncio.Event()
        self.player_skip = asyncio.Event()
        self.player_task = asyncio.create_task(
            self.__player())  # self.player_event

        self.queue = Queue()

        self.song = None  # = self.queue.get(0)#this will
        # To avoid ^ erroring maybe force Player to be initialized with a Song or Queue?

        self.last_np_message = None

        self.looping = False
        self.queue_looping = False

        self.vc = vc

    # Private method to generate and send a now_playing message
    # Yes, I know this is a bunch of code from musS_D but it would have
    # been so much harder to implement a listener than to do this
    async def __send_np(self, song: Song) -> None:
        random.seed(song.id)
        color = random.randint(0, 16777215)
        title_message = f'Now Playing:\t{":repeat: " if self.looping else ""}{":repeat_one: " if self.queue_looping else ""}'
        embed = discord.Embed(
            title=title_message,
            url=song.original_url,
            description=f'{song.title} -- {song.uploader}',
            color=color
        )
        embed.add_field(name='Duration:', value=song.parse_duration(
            song.duration), inline=True)
        embed.add_field(name='Requested by:', value=song.requester.mention)
        embed.set_image(url=song.thumbnail)
        embed.set_author(name=song.requester.display_name,
                         icon_url=song.requester.display_avatar.url)
        # Delete last now_playing if there is one
        if self.last_np_message is not None:
            await self.last_np_message.delete()
        self.last_np_message = await self.vc.channel.send(embed=embed)

    async def __player(self) -> None:
        print("Initializing Player.")
        await self.player_event.wait()
        print("Player has been given GO signal")
        # This while will immediately terminate when player_abort is set.
        # If it doesn't abort, swap back to threading.Event instead of asyncio

        # I still haven't properly tested if this abort method works so if it's misbehaving this is first on the chopping block
        while not self.player_abort.is_set():

            # Allows __player to terminate without "aborting"
            while not self.player_skip.is_set():

                # Get the top song in queue ready to play
                await self.queue.get(0).populate()

                # Just to be safe and make sure we don't
                # cut off anything early, do a quick is_playing loop
                while self.vc.is_playing():
                    await asyncio.sleep(1)

                # Set the now-populated top song to the playing song
                self.song = self.queue.get(0)

                await self.__send_np(self.song)

                # Begin playing audio into Discord

                self.song.start()

                self.vc.play(discord.FFmpegPCMAudio(
                    self.song.audio, **YTDLInterface.ffmpeg_options
                ))

                # Sleep player until song ends
                await asyncio.sleep(self.song.duration)
                # If song is looping, continue from top
                if self.looping:
                    continue

                self.queue.remove(0)

                # If we're queue looping, re-add the removed song to top of queue
                if self.queue_looping:
                    self.queue.add(self.song)
                    continue

                # Check if the queue is empty
                if not self.queue.get():
                    # Just to be safe and make sure we don't
                    # cut off anything early, do a quick is_playing loop
                    while self.vc.is_playing():
                        await asyncio.sleep(1)
                    # Abort the player
                    self.player_abort.set()

            self.player_skip.unset()

        # Delete a to-be defunct now_playing message
        if self.last_np_message:
            await self.last_np_message.delete()
        # Signal to everything else that player has ended
        self.player_abort.set()

    # Start player and return upon it's death
    async def start(self) -> None:
        self.player_event.set()
        await self.player_abort.wait()
        return

    def is_started(self) -> bool:
        return self.player_event.is_set()

    def terminate_player(self) -> None:
        self.player_abort.set()

    def skip_player(self) -> None:
        self.player_skip.set()

    def set_loop(self, state: bool) -> None:
        self.looping = state

    def set_queue_loop(self, state: bool) -> None:
        self.queue_looping = state
