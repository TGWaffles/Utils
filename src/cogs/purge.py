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

    @commands.group(pass_context=True, aliases=["clear", "clean", "wipe", "delete"])
    @is_staff()
    async def purge(self, ctx: commands.Context):
        if ctx.invoked_subcommand is None:
            message: discord.Message = ctx.message
            message.application = {"original_content": message.content}
            message.content = "u!purge_internal " + message.content.partition(f"{ctx.invoked_with} ")[2]
            await self.bot.process_commands(message)

    @commands.command()
    @is_staff()
    async def purge_internal(self, ctx, amount: int = None, disable_bulk: bool = False,
                             member: Optional[discord.Member] = None):
        guild_doc = await self.bot.mongo.find_by_id(self.bot.mongo.discord_db.guilds, ctx.guild.id)
        purge_max = guild_doc.get("purge_max", 40)
        bulk = True
        check = check_pinned
        if not ctx.author.guild_permissions.administrator and not (purge_max > amount > 0):
            await ctx.reply(embed=self.bot.create_error_embed(messages.purge_limit.format(purge_max)))
            return
        if ctx.author.guild_permissions.administrator and disable_bulk:
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
                if member is not None:
                    true_amount = len([message for message in await ctx.message.channel.history(limit=amount).flatten()
                                       if check(message)])
                else:
                    true_amount = amount
                if true_amount < amount:
                    to_send = "{} of {}".format(true_amount, amount)
                else:
                    to_send = amount
                response = await self.bot.ask_boolean(ctx, ctx.author, question=self.bot.create_processing_embed(
                    "Confirm", "Are you sure you want to clear **{}** messages?\n(type \"yes\" to confirm)".format(
                        to_send)))
                if not response:
                    return
                await response.delete()
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

    @purge.command(aliases=["max"])
    async def maximum(self, ctx, maximum: int):
        await self.bot.mongo.discord_db.guilds.update_one({"_id": ctx.guild.id}, {"$set": {"purge_max": maximum}})
        await ctx.reply(embed=self.bot.create_completed_embed("Set Purge Maximum", f"New purge maximum is {maximum}!"))


def setup(bot):
    cog = Purge(bot)
    bot.add_cog(cog)
