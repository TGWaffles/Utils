from typing import Optional

import discord
from discord.ext import commands

from main import UtilsBot
from src.checks.message_check import check_pinned
from src.checks.role_check import is_staff
from src.storage import config, messages


class Purge(commands.Cog):
    def __init__(self, bot: UtilsBot):
        self.bot: UtilsBot = bot

    @commands.command(pass_context=True, aliases=["clear", "clean", "wipe", "delete"])
    @is_staff()
    async def purge(self, ctx, amount: int = None, disable_bulk: bool = False, member: Optional[discord.Member] = None):
        bulk = True
        check = check_pinned
        if ctx.message.author.id != config.owner_id and not (config.purge_max > amount > 0):
            await ctx.reply(embed=self.bot.create_error_embed(messages.purge_limit))
            return
        if ctx.message.author.id == config.owner_id and disable_bulk:
            bulk = False
            check = lambda x: True
        if member is not None:
            old_check = check
            check = lambda x: old_check(x) and x.author.id == member.id
        if amount is None:
            await ctx.reply(embed=self.bot.create_error_embed(messages.no_purge_amount))
            return
        if amount == -1:
            response = await self.bot.ask_boolean(ctx, ctx.author, question=self.bot.create_processing_embed(
                "Confirm", "Are you sure you want to clear the whole channel...?"))
            if not response:
                return
            await ctx.message.channel.purge(limit=None, bulk=bulk, check=check)
        else:
            if amount > config.confirm_amount:
                true_amount = len([message for message in await ctx.message.channel.history(limit=amount).flatten()
                                   if check(message)])
                if true_amount < amount:
                    to_send = "{} of {}".format(true_amount, amount)
                else:
                    to_send = amount
                response = await self.bot.ask_boolean(ctx, ctx.author, question=self.bot.create_processing_embed(
                    "Confirm", "Are you sure you want to clear **{}** messages?\n(type \"yes\" to confirm)".format(
                        to_send)))
                if not response:
                    return
                while True:
                    try:
                        await ctx.message.channel.purge(limit=amount + 3, bulk=bulk, check=check)
                        break
                    except discord.NotFound:
                        pass
            else:
                while True:
                    try:
                        await ctx.message.channel.purge(limit=amount + 1, bulk=bulk, check=check)
                        break
                    except discord.NotFound:
                        pass


def setup(bot):
    cog = Purge(bot)
    bot.add_cog(cog)
