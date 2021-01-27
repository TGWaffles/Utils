import datetime

import dateparser
import discord
from discord.ext import commands

from main import UtilsBot
from src.checks.role_check import is_high_staff
from src.checks.user_check import is_owner
from src.helpers.storage_helper import DataHelper


class OGCog(commands.Cog):
    def __init__(self, bot: UtilsBot):
        self.bot: UtilsBot = bot
        self.data = DataHelper()

    def is_og(self, member: discord.Member):
        assert str(member.guild.id) in self.data.get("og_dates", {}).keys()
        og_date = datetime.datetime.utcfromtimestamp(self.data.get("og_dates", {}).get(str(member.guild.id)))
        first_join_date = member.joined_at
        # noinspection SpellCheckingInspection
        first_join_date = first_join_date.replace(tzinfo=datetime.timezone.utc)
        return first_join_date < og_date

    @commands.command(pass_context=True)
    async def check_og(self, ctx, member: discord.Member = None):
        if member is None:
            member = ctx.message.author
        if self.data.get("og_dates", {}).get(str(ctx.guild.id), None) is None:
            await ctx.reply(embed=self.bot.create_error_embed("There is no defined OG date in this guild!"))
            return
        is_og = self.is_og(member)
        message_time = None
        data = DataHelper()
        all_guilds = data.get("og_messages", {})
        og_messages = all_guilds.get(str(member.guild.id))
        if str(member.id) in og_messages.keys():
            is_og = True
            message_time = datetime.datetime.utcfromtimestamp(og_messages.get(str(member.id), 0))
        embed = discord.Embed(title="OG Check")
        embed.set_author(name=member.name, icon_url=member.avatar_url)
        embed.description = "{} Member {} OG".format(("❌", "✅")[int(is_og)], ("is not", "is")[int(is_og)])
        embed.colour = (discord.Colour.red(), discord.Colour.green())[int(is_og)]
        embed.timestamp = member.joined_at
        if message_time is not None:
            embed.timestamp = message_time
            embed.add_field(name="First Message", value=message_time.strftime("%Y-%m-%d %H:%M"))
        if self.bot.latest_joins == {}:
            await self.bot.get_latest_joins()
        members = self.bot.latest_joins[ctx.guild.id]
        members = [user.id for user in members]
        embed.add_field(name="Position", value="#{}".format(str(members.index(member.id) + 1)))
        await ctx.reply(embed=embed)

    @commands.command(pass_context=True)
    @is_owner()
    async def all_ogs(self, ctx, reset: bool):
        if self.data.get("og_dates", {}).get(str(ctx.guild.id), None) is None:
            await ctx.reply(embed=self.bot.create_error_embed("There is no defined OG date in this guild!"))
            return
        og_date = datetime.datetime.utcfromtimestamp(self.data.get("og_dates", {}).get(str(ctx.guild.id), None))
        if self.data.get("og_roles", {}).get(str(ctx.guild.id), None) is None:
            await ctx.reply(embed=self.bot.create_error_embed("There is no defined OG role for this guild!"))
            return
        og_role = ctx.guild.get_role(self.data.get("og_roles", {}).get(str(ctx.guild.id), None))
        message_member_ids = {}
        start_embed = discord.Embed(title="Doing all OGs.", description="I will now start to process all messages "
                                                                        "until the predefined OG date.",
                                    colour=discord.Colour.orange())
        processing_message = await ctx.reply(embed=start_embed)
        last_edit = datetime.datetime.now()
        for channel in ctx.guild.text_channels:
            async for message in channel.history(limit=None, before=og_date.replace(tzinfo=None), oldest_first=True):
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
        if reset:
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
        data = DataHelper()
        all_guilds = data.get("og_messages", {})
        all_guilds[str(ctx.guild.id)] = message_member_ids
        data["og_messages"] = all_guilds

    @commands.command()
    @is_high_staff()
    async def set_og_date(self, ctx, og_date: str):
        set_date = dateparser.parse(og_date)
        if set_date is None:
            await ctx.reply(embed=self.bot.create_error_embed("That couldn't be interpreted as a valid date."))
            return
        if set_date.tzinfo is None:
            await ctx.reply(embed=self.bot.create_error_embed("Please specify a timezone!"))
            return
        all_guilds = self.data.get("og_dates", {})
        all_guilds[str(ctx.guild.id)] = set_date.timestamp()
        self.data["og_dates"] = all_guilds
        await ctx.reply(embed=self.bot.create_completed_embed("OG Date Set!",
                                                              "OG date was successfully set to: {}.".format(
                                                                  set_date.strftime("%Y-%m-%d %H:%M"))))

    @commands.command()
    @is_high_staff()
    async def set_og_role(self, ctx, og_role: discord.Role):
        all_guilds = self.data.get("og_roles", {})
        all_guilds[str(ctx.guild.id)] = og_role.id
        self.data["og_roles"] = all_guilds


def setup(bot):
    cog = OGCog(bot)
    bot.add_cog(cog)
