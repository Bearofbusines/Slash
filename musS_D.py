import asyncio
import discord
import os
import random
from datetime import datetime
from dotenv import load_dotenv


load_dotenv()  # getting the key from the .env file
key = os.environ.get('key')


def pront(content, lvl="DEBUG", end="\n"):
    colors = {
        "LOG": "",
        "DEBUG": "\033[1;95m",
        "OKBLUE": "\033[94m",
        "OKCYAN": "\033[96m",
        "OKGREEN": "\033[92m",
        "WARNING": "\033[93m",
        "ERROR": "\033[91m",
        "NONE": "\033[0m"
    }
    # if type(content) != str and type(content) != int and type(content) != float:
    #    content = sep.join(content)
    print(colors[lvl] + "{" + datetime.now().strftime("%x %X") +
          "} " + lvl + ": " + str(content) + colors["NONE"], end=end)  # sep.join(list())


# Returns a random hex code
async def getRandomHex(seed):
    random.seed(seed)
    return random.randint(0, 16777215)


# Creates a standard Embed object
async def getEmbed(interaction, title='', content='', footer='', color=''):
    if color == '':
        color = await getRandomHex(interaction.user.id)
    embed = discord.Embed(
        title=title,
        description=content,
        color=color
    )
    embed.set_author(name=interaction.user.display_name,
                     icon_url=interaction.user.display_avatar.url)
    # TODO Hide the footer until i find out what to do with it
    # embed.set_footer(footer=footer)
    return embed


# Creates and sends an Embed message
async def send(interaction, title='', content='', footer='', color='', ephemeral: bool=False):
    embed = await getEmbed(interaction, title, content, footer)
    await interaction.response.send_message(embed=embed, ephemeral=ephemeral)


class Bot(discord.Client):
    def __init__(self):
        super().__init__(intents=discord.Intents(value=3467840))
        self.synced = False

    async def on_ready(self):
        await self.wait_until_ready()
        if not self.synced:
            await tree.sync()
            self.synced = True
        pront("Bot is ready", lvl="OKGREEN")


bot = Bot()
tree = discord.app_commands.CommandTree(bot)



## COMMANDS ##



@tree.command(name="ping", description="The ping command")
async def _ping(interaction: discord.Interaction):
    pront(dir(interaction), end="\n\n")
    pront(dir(interaction.channel), end="\n\n")
    pront(dir(interaction.client), end="\n\n")
    pront(dir(interaction.user), end="\n\n")
    # await send(interaction, title='Pong!', content=':ping_pong:')
    await interaction.response.send_message('Pong!', ephemeral=True)


bot.run(key)