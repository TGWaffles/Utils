import asyncio

import discord

from discord.ext import commands
from src.main import UtilsBot
from src.checks.role_check import is_high_staff
from src.storage import config, messages

def check_reply(message):
    return message.author.id == config.owner_id and message.content == "yes"


class Purge(commands.Cog):
    def __init__(self, bot: UtilsBot):
        self.bot: UtilsBot = bot

    @commands.command(pass_context=True)
    @is_high_staff()
    async def purge(self, ctx, amount: int = None):
        if ctx.message.author.id != config.owner_id and (config.purge_max > amount > 0):
            await ctx.send(embed=self.bot.create_error_embed(messages.purge_limit))
            return
        if amount is None:
            await ctx.send(embed=self.bot.create_error_embed(messages.no_purge_amount))
            return
        if amount == -1:
            sent = await ctx.send(embed=self.bot.create_processing_embed("Confirm", "Are you sure you want to "
                                                                                    "clear the whole channel...?"))
            try:
                await self.bot.wait_for("message", check=check_reply, timeout=60.0)
            except asyncio.TimeoutError:
                await sent.edit(embed=self.bot.create_error_embed("This is a good thing. Crisis averted."))
        else:
            await ctx.message.channel.purge(limit=amount, bulk=True)


def setup(bot):
    cog = Purge(bot)
    bot.add_cog(cog)
