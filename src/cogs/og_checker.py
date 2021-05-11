import datetime

import dateparser
import discord
import pymongo
from discord.ext import commands
from typing import Optional

from main import UtilsBot
from src.checks.role_check import is_high_staff
from src.helpers.storage_helper import DataHelper
from src.checks.user_check import is_owner


class OGCog(commands.Cog):
    def __init__(self, bot: UtilsBot):
        self.bot: UtilsBot = bot
        self.og_coll = self.bot.mongo.discord_db.og

    async def is_og(self, member: discord.Member):
        guild_document = await self.og_coll.find_one({"_id": member.guild.id})
        assert guild_document is not None and guild_document.get("date", None) is not None
        og_date = guild_document.get("date").replace(tzinfo=datetime.timezone.utc)
        earliest_message = await self.bot.mongo.discord_db.messages.find_one({"user_id": member.id,
                                                                              "guild_id": member.guild.id},
                                                                             sort=[("created_at", pymongo.ASCENDING)])
        first_join_date = member.joined_at
        # noinspection SpellCheckingInspection
        first_join_date = first_join_date.replace(tzinfo=datetime.timezone.utc)
        if earliest_message is not None:
            first_message_date = earliest_message.get("created_at").replace(tzinfo=datetime.timezone.utc)
            return first_message_date < og_date or first_join_date < og_date
        return first_join_date < og_date

    @commands.command(pass_context=True, aliases=["og_check"])
    async def check_og(self, ctx, member: discord.Member = None):
        if member is None:
            member = ctx.message.author
        guild_document = await self.og_coll.find_one({"_id": member.guild.id})
        if guild_document is None or guild_document.get("date", None) is None:
            await ctx.reply(embed=self.bot.create_error_embed("There is no defined OG date in this guild!"))
            return
        is_og = await self.is_og(member)
        message_time = None
        earliest_message = await self.bot.mongo.discord_db.messages.find_one({"user_id": member.id,
                                                                              "guild_id": ctx.guild.id,
                                                                              "deleted": False},
                                                                             sort=[("created_at", pymongo.ASCENDING)])
        if earliest_message is not None:
            message_time = earliest_message.get("created_at").replace(tzinfo=datetime.timezone.utc)
        embed = discord.Embed(title="OG Check")
        embed.set_author(name=member.name, icon_url=member.avatar_url)
        embed.description = "{} Member {} OG".format(("❌", "✅")[int(is_og)], ("is not", "is")[int(is_og)])
        embed.colour = (discord.Colour.red(), discord.Colour.green())[int(is_og)]
        embed.timestamp = member.joined_at
        if message_time is not None:
            # Check that message time is actually earlier than joined_at before replacing it.
            if message_time.replace(tzinfo=datetime.timezone.utc) < member.joined_at.replace(
                    tzinfo=datetime.timezone.utc):
                embed.timestamp = message_time
            embed.add_field(name="First Message", value=message_time.strftime("%Y-%m-%d %H:%M"))
        if self.bot.latest_joins == {} or ctx.guild.id not in self.bot.latest_joins:
            await self.bot.get_latest_joins()
        members = self.bot.latest_joins[ctx.guild.id]
        members = [user.id for user in members]
        embed.add_field(name="Position", value="#{}".format(str(members.index(member.id) + 1)))
        await ctx.reply(embed=embed)

    # noinspection DuplicatedCode
    @commands.command()
    @is_high_staff()
    async def fast_ogs(self, ctx):
        guild_document = await self.og_coll.find_one({"_id": ctx.guild.id})
        if guild_document is None:
            await ctx.reply(embed=self.bot.create_error_embed("There is no OG date or role in this guild! "
                                                              "Use !set_og_date and !set_og_role to set them!"))
            return
        if guild_document.get("date", None) is None:
            await ctx.reply(embed=self.bot.create_error_embed("There is no defined OG date in this guild!"))
            return
        og_date = guild_document.get("date")
        if guild_document.get("role_id", None) is None:
            await ctx.reply(embed=self.bot.create_error_embed("There is no defined OG role for this guild!"))
            return
        og_role = ctx.guild.get_role(guild_document.get("role_id"))
        processing_message = await ctx.reply(embed=self.bot.create_processing_embed("Processing messages",
                                                                                    "Checking who sent the OG messages "
                                                                                    "in this guild."))
        last_edit = datetime.datetime.now()
        pipeline = [
            {
                "$match": {
                    "guild_id": ctx.guild.id,
                    "created_at": {"$lt": og_date}
                }
            },
            {
                "$project": {
                    "_id": "$user_id"
                }
            }
        ]
        og_date = og_date.replace(tzinfo=datetime.timezone.utc)
        aggregation = self.bot.mongo.discord_db.messages.aggregate(pipeline=pipeline)
        og_users = [x.get("_id") for x in await aggregation.to_list(length=None)]
        async for member in ctx.guild.fetch_members(limit=None):
            is_og = member.id in og_users or member.joined_at.replace(tzinfo=datetime.timezone.utc) < og_date
            if (datetime.datetime.now() - last_edit).total_seconds() > 1:
                embed = discord.Embed(title="Processing Members...",
                                      description="Last Member: {}. "
                                                  "Joined at: {}. "
                                                  "Is OG: {}".format(member.name,
                                                                     member.joined_at.strftime("%Y-%m-%d %H:%M"),
                                                                     is_og),
                                      colour=discord.Colour.orange())
                embed.set_author(name=member.name, icon_url=member.avatar_url)
                embed.timestamp = member.joined_at.replace(tzinfo=None)
                await processing_message.edit(embed=embed)
                last_edit = datetime.datetime.now()
            if is_og:
                try:
                    await member.add_roles(og_role)
                except Exception as e:
                    print(e)

    # noinspection DuplicatedCode
    @commands.command(pass_context=True)
    @is_high_staff()
    async def all_ogs(self, ctx, reset: Optional[bool]):
        guild_document = await self.og_coll.find_one({"_id": ctx.guild.id})
        if guild_document is None:
            await ctx.reply(embed=self.bot.create_error_embed("There is no OG date or role in this guild! "
                                                              "Use !set_og_date and !set_og_role to set them!"))
            return
        if guild_document.get("date", None) is None:
            await ctx.reply(embed=self.bot.create_error_embed("There is no defined OG date in this guild!"))
            return
        og_date = guild_document.get("date")
        og_date = og_date.replace(tzinfo=datetime.timezone.utc)
        if guild_document.get("role_id", None) is None:
            await ctx.reply(embed=self.bot.create_error_embed("There is no defined OG role for this guild!"))
            return
        og_role = ctx.guild.get_role(guild_document.get("role_id"))
        message_member_ids = {}
        start_embed = discord.Embed(title="Doing all OGs.", description="I will now start to process all messages "
                                                                        "until the predefined OG date.",
                                    colour=discord.Colour.orange())
        processing_message = await ctx.reply(embed=start_embed)
        last_edit = datetime.datetime.now()
        for channel in ctx.guild.text_channels:
            async for message in channel.history(limit=None, before=og_date.replace(tzinfo=None), oldest_first=True):
                await self.bot.mongo.insert_message(message)
                author = message.author
                if (datetime.datetime.now() - last_edit).total_seconds() > 1:
                    embed = discord.Embed(title="Processing messages",
                                          description="Last Message text: {}, from {}, in {}".format(
                                              message.clean_content, message.created_at.strftime("%Y-%m-%d %H:%M"),
                                              channel.mention), colour=discord.Colour.orange())
                    embed.set_author(name=author.name, icon_url=author.avatar_url)
                    embed.timestamp = message.created_at
                    await processing_message.edit(embed=embed)
                    last_edit = datetime.datetime.now()
                if str(author.id) not in message_member_ids.keys():
                    join_date = message.created_at.replace(tzinfo=datetime.timezone.utc)
                    message_member_ids[str(author.id)] = join_date.timestamp()
        if reset is not None and reset:
            starting_reset = discord.Embed(title="Finished messages.", description="I have processed messages. I will "
                                                                                   "now remove the OG role from all "
                                                                                   "members.",
                                           colour=discord.Colour.orange())
            await processing_message.edit(embed=starting_reset)
            for member in ctx.guild.members:
                if og_role in member.roles:
                    if (datetime.datetime.now() - last_edit).total_seconds() > 1:
                        embed = discord.Embed(title="Removing OG role from all members...",
                                              description="Current member: {}".format(member.name),
                                              colour=discord.Colour.orange())
                        await processing_message.edit(embed=embed)
                    try:
                        await member.remove_roles(og_role)
                    except Exception as e:
                        print(e)
        messages_done = discord.Embed(title="Finished Messages.", description="Finished messages. I will now start to "
                                                                              "apply the OG role to all deserving "
                                                                              "users.", colour=discord.Colour.orange())
        await processing_message.edit(embed=messages_done)
        last_edit = datetime.datetime.now()
        members_processed = 0
        async for member in ctx.guild.fetch_members(limit=None):
            has_message = str(member.id) in message_member_ids.keys()
            if has_message:
                message_creation_date = datetime.datetime.fromtimestamp(message_member_ids[str(member.id)],
                                                                        datetime.timezone.utc)
                message_creation_message = message_creation_date.strftime("%Y-%m-%d %H:%M")
                join_time = min(message_creation_date,
                                member.joined_at.replace(tzinfo=datetime.timezone.utc))
            else:
                message_creation_message = "No"
                join_time = member.joined_at.replace(tzinfo=datetime.timezone.utc)
            is_og = join_time < og_date
            if (datetime.datetime.now() - last_edit).total_seconds() > 1:
                embed = discord.Embed(title="Processing Members...",
                                      description="Last Member: {}. "
                                                  "Joined at: {}. "
                                                  "Has previous message: {}."
                                                  "Is OG: {}".format(member.name,
                                                                     member.joined_at.strftime("%Y-%m-%d %H:%M"),
                                                                     message_creation_message,
                                                                     is_og),
                                      colour=discord.Colour.orange())
                embed.set_author(name=member.name, icon_url=member.avatar_url)
                embed.timestamp = join_time.replace(tzinfo=None)
                await processing_message.edit(embed=embed)
                last_edit = datetime.datetime.now()
            if is_og:
                try:
                    await member.add_roles(og_role)
                except Exception as e:
                    print(e)
                members_processed += 1
        embed = self.bot.create_completed_embed("Completed OG addition", "Successfully added all OGs!")
        await processing_message.edit(embed=embed)

    @commands.command()
    @is_high_staff()
    async def set_og_date(self, ctx, *, og_date: str):
        set_date = dateparser.parse(og_date)
        if set_date is None:
            await ctx.reply(embed=self.bot.create_error_embed("That couldn't be interpreted as a valid date."))
            return
        if set_date.tzinfo is None:
            await ctx.reply(embed=self.bot.create_error_embed("Please specify a timezone!"))
            return
        guild_document = await self.og_coll.find_one({"_id": ctx.guild.id})
        if guild_document is None:
            guild_document = {"_id": ctx.guild.id}
        guild_document["date"] = set_date
        await self.bot.mongo.force_insert(self.og_coll, guild_document)
        await ctx.reply(embed=self.bot.create_completed_embed("OG Date Set!",
                                                              "OG date was successfully set to: {}.".format(
                                                                  set_date.strftime("%Y-%m-%d %H:%M"))))

    @commands.command()
    @is_high_staff()
    async def set_og_role(self, ctx, og_role: discord.Role):
        guild_document = await self.og_coll.find_one({"_id": ctx.guild.id})
        if guild_document is None:
            guild_document = {"_id": ctx.guild.id}
        guild_document["role_id"] = og_role.id
        await self.bot.mongo.force_insert(self.og_coll, guild_document)
        await ctx.reply(embed=self.bot.create_completed_embed("Set OG Role!",
                                                              "OG Role has been set to {}!".format(
                                                                  og_role.mention)))


def setup(bot):
    cog = OGCog(bot)
    bot.add_cog(cog)
