import datetime

import discord
from discord.ext import commands
from src.storage import config
from src.checks.role_check import is_staff
from main import UtilsBot


class Blacklist(commands.Cog):
    def __init__(self, bot: UtilsBot):
        self.bot: UtilsBot = bot

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.bot:
            return

        if is_staff():
            return

        contents: str = message.contents
        if "cantswim" in ''.join(filter(str.isalpha, contents)):
            await message.delete()


def setup(bot):
    cog = Blacklist(bot)
    bot.add_cog(cog)

