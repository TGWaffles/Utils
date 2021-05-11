import datetime
from typing import Optional

import discord
import pymongo
from discord.ext import commands

from main import UtilsBot
from src.storage import config


class Reputation(commands.Cog):
    def __init__(self, bot: UtilsBot):
        self.bot = bot
        self.reputation_coll = self.bot.mongo.discord_db.reputation

    async def count_given(self, user: discord.User, timeframe: Optional[datetime.timedelta]):
        if timeframe is None:
            timeframe = datetime.timedelta(days=7)
        after = datetime.datetime.now() - timeframe
        count = await self.reputation_coll.count_documents({"sender_id": user.id, "timestamp": {"$gt": after}})
        return count

    async def get_last_rep(self, user_from: discord.User, user_to: discord.User):
        last_rep = await self.reputation_coll.find_one({"sender_id": user_from.id, "user_id": user_to.id},
                                                       sort=[("timestamp", pymongo.ASCENDING)])
        return last_rep

    @commands.command(name="Rep", description="Add positive/negative rep to a user!",
                      aliases=["reputation", "add_rep", "unrep", "remove_rep", "derep", "addrep", "removerep"])
    async def rep(self, ctx, user: discord.User, reputation_type: Optional[str], *, reason: Optional[str] = ""):
        async with ctx.typing():
            if reputation_type is None:
                positive = True
            elif reputation_type.lower() in ["neg", "negative", "remove", "n", "no", "take", "delete", "bad"]:
                positive = False
            elif reputation_type.lower() in ["pos", "positive", "add", "y", "yes", "give", "apply", "good"]:
                positive = True
            else:
                await ctx.reply(
                    embed=self.bot.create_error_embed("Unknown reputation type. "
                                                      "Please use positive/negative.\n"
                                                      f"Usage: \"{self.bot.get_guild_prefix(ctx.guild)}rep "
                                                      f"<user> [positive/negative] [reason]\" (no need for <> "
                                                      f"or [], they represent compulsory or optional arguments,"
                                                      f" respectively)\n"
                                                      "For example, !rep @Test positive For helping me learn!"))
                return
            given_count = await self.count_given(ctx.author, datetime.timedelta(days=config.limit_period_days))
            if given_count >= config.limit_amount:
                await ctx.reply(embed=self.bot.create_error_embed(f"You have already given your maximum of "
                                                                  f"{config.limit_amount} reputation this week!"))
                return
            last_rep = await self.get_last_rep(ctx.author, user)
            if last_rep is not None:
                delta_since_last = (datetime.datetime.now() - last_rep.get("timestamp"))
                seconds_since_last = delta_since_last.total_seconds()
                hours_since_last = seconds_since_last / 3600
                if hours_since_last < 24:
                    await ctx.reply(
                        embed=self.bot.create_error_embed(f"You have already given {user.name} rep in the last "
                                                          f"24 hours! \nPlease wait {delta_since_last} until "
                                                          f"next giving rep!"))
                    return
            rep_document = {"user_id": user.id, "sender_id": ctx.author.id, "reason": reason, "positive": positive,
                            "timestamp": datetime.datetime.now()}
            await self.bot.mongo.force_insert(self.reputation_coll, rep_document)
            user_rep_positive = await self.reputation_coll.count_documents({"user_id": user.id, "positive": True})
            user_rep_negative = await self.reputation_coll.count_documents({"user_id": user.id, "positive": False})
            embed = self.bot.create_completed_embed("Reputation Added!", "")
            embed.description = (
                f"Reputation added to {user.name}.\nYou have {config.limit_amount - (given_count + 1)} "
                f"reputation left to give this week.\n\n**New Rep For {user.name}**")
            embed.add_field(name="✅", value=user_rep_positive, inline=True)
            embed.add_field(name="❌", value=user_rep_negative, inline=True)
            embed.set_author(name=user.name, icon_url=user.avatar_url)
            await ctx.reply(embed=embed)

    @commands.command(name="info", description="See reputation info for a user!",
                      aliases=["rinfo", "repinfo", "reputation_info", "rep_info", "reputationinfo"])
    async def info(self, ctx, user: Optional[discord.User]):
        async with ctx.typing():
            if user is None:
                user = ctx.author
            user_rep_positive = await self.reputation_coll.count_documents({"user_id": user.id, "positive": True})
            user_rep_negative = await self.reputation_coll.count_documents({"user_id": user.id, "positive": False})
            embed = discord.Embed(title=f"Reputation Information for {user.name}")
            if user_rep_positive > user_rep_negative:
                embed.colour = discord.Colour.green()
            elif user_rep_positive == user_rep_negative:
                embed.colour = discord.Colour.orange()
            else:
                embed.colour = discord.Colour.red()
            embed.add_field(name="✅", value=user_rep_positive, inline=True)
            embed.add_field(name="❌", value=user_rep_negative, inline=True)
            embed.set_author(name=user.name, icon_url=user.avatar_url)
            reputations = self.reputation_coll.find({"user_id": user.id}).sort("timestamp", -1).limit(5)
            if reputations is None:
                reputations = []
            async for reputation in reputations:
                try:
                    user = await self.bot.fetch_user(reputation.get("sender_id"))
                    username = user.name
                except discord.errors.Forbidden:
                    username = f"Unknown User ({reputation.get('sender_id')})"
                field_name = "{} - {} - {}".format(username, reputation.get("timestamp").strftime("%Y-%m-%d %H:%M:%S"),
                                                   ("-1", "+1")[int(reputation.get("positive"))])
                reason = reputation.get("reason")
                if reason == "":
                    reason = "No Reason"
                embed.add_field(name=field_name, value=reason, inline=False)
            await ctx.reply(embed=embed)


def setup(bot):
    cog = Reputation(bot)
    bot.add_cog(cog)
