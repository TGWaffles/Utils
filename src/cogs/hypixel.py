import discord
import datetime
import asyncio

from src.storage import config, messages
from discord.ext import commands
from main import UtilsBot
from src.checks.role_check import is_staff
from src.checks.user_check import is_owner
from src.checks.guild_check import monkey_check
from src.checks.message_check import check_reply


class Hypixel(commands.Cog):
    def __init__(self, bot: UtilsBot):
        self.bot: UtilsBot = bot

    @commands.command(pass_context=True)
    async def hypixel_channel(self, ctx, channel: discord.TextChannel):
        sent = await ctx.send(embed=self.bot.create_processing_embed("Confirm", "Are you sure you want to make {} "
                                                                                "the text channel for hypixel "
                                                                                "updates? \n "
                                                                                "(THIS DELETES ALL CONTENTS) \n"
                                                                                "Type \"yes\" if you're sure."))
        try:
            await self.bot.wait_for("message", check=check_reply(ctx.message.author), timeout=15.0)
        except asyncio.TimeoutError:
            return


def setup(bot):
    cog = Hypixel(bot)
    bot.add_cog(cog)
