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
        return
        # if message.author.bot:
        #     return
        # print("running blacklist check...")
        # if (config.staff_role_id in [role.id for role in message.author.roles] or
        #         message.author.guild_permissions.administrator):
        #     return
        # contents: str = message.content
        # print(''.join(filter(str.isalpha, contents)))
        # if "cantswim" in ''.join(filter(str.isalpha, contents)):
        #     print("it's in...")
        #     await message.delete()


def setup(bot):
    cog = Blacklist(bot)
    bot.add_cog(cog)

