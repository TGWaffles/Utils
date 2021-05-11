import asyncio

from discord.ext import commands

from main import UtilsBot
from src.checks.user_check import is_owner
from src.checks.role_check import is_high_staff


class CommandManager(commands.Cog):
    def __init__(self, bot: UtilsBot):
        self.bot = bot



def setup(bot):
    cog = CommandManager(bot)
    bot.add_cog(cog)

