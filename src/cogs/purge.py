import asyncio

import discord

from discord.ext import commands
from main import UtilsBot
from src.checks.role_check import is_staff
from src.storage import config, messages


def check_reply(author):
    def check_author(message):
        return message.author.id == author.id and message.content.lower() == "yes"
    return check_author


def check_pinned(message):
    return not message.pinned


class Purge(commands.Cog):
    def __init__(self, bot: UtilsBot):
        self.bot: UtilsBot = bot

    @commands.command(pass_context=True)
    @is_staff()
    async def purge(self, ctx, amount: int = None, disable_bulk: bool = False):
        bulk = True
        check = check_pinned
        if ctx.message.author.id != config.owner_id and not (config.purge_max > amount > 0):
            await ctx.send(embed=self.bot.create_error_embed(messages.purge_limit))
            return
        if ctx.message.author.id == config.owner_id and disable_bulk:
            bulk = False
            check = lambda x: True
        if amount is None:
            await ctx.send(embed=self.bot.create_error_embed(messages.no_purge_amount))
            return
        if amount == -1:
            sent = await ctx.send(embed=self.bot.create_processing_embed("Confirm", "Are you sure you want to "
                                                                                    "clear the whole channel...?"))
            try:
                await self.bot.wait_for("message", check=check_reply(ctx.message.author), timeout=15.0)
                await ctx.message.channel.purge(limit=None, bulk=bulk, check=check)
            except asyncio.TimeoutError:
                await sent.edit(embed=self.bot.create_error_embed("This is a good thing. Crisis averted."))
        else:
            if amount > config.confirm_amount:
                sent = await ctx.send(embed=self.bot.create_processing_embed("Confirm", "Are you sure you want to "
                                                                                        "clear **{}** messages?\n"
                                                                                        "(type \"yes\" to confirm)".
                                                                             format(amount)))
                try:
                    await self.bot.wait_for("message", check=check_reply(ctx.message.author), timeout=15.0)
                    try:
                        await ctx.message.channel.purge(limit=amount + 3, bulk=bulk, check=check)
                    except discord.NotFound:
                        pass
                except asyncio.TimeoutError:
                    await sent.edit(embed=self.bot.create_error_embed("Purge wasn't confirmed by the user."))
            else:
                try:
                    await ctx.message.channel.purge(limit=amount + 1, bulk=bulk, check=check)
                except discord.NotFound:
                    pass


def setup(bot):
    cog = Purge(bot)
    bot.add_cog(cog)
