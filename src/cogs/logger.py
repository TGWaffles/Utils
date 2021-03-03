import asyncio
import re
import time
from concurrent.futures import ThreadPoolExecutor, ProcessPoolExecutor
from functools import partial
from typing import Optional

import discord
import src.storage.config as config
from discord.ext import commands, tasks

from main import UtilsBot
from src.checks.user_check import is_owner
from src.helpers.sqlalchemy_helper import DatabaseHelper
from src.helpers.storage_helper import DataHelper


class SQLAlchemyTest(commands.Cog):
    def __init__(self, bot: UtilsBot):
        self.bot = bot
        self.database = DatabaseHelper()
        self.bot.loop.run_in_executor(None, self.database.ensure_db)
        self.last_update = self.bot.create_processing_embed("Working...", "Starting processing!")
        self.channel_update = self.bot.create_processing_embed("Working...", "Starting processing!")
        self.data = DataHelper()
        self.update_motw.start()

    async def send_update(self, sent_message):
        if len(self.last_update.description) < 2000:
            await sent_message.edit(embed=self.last_update)

    async def send_channel_update(self, sent_message):
        while True:
            try:
                if len(self.channel_update) < 2000:
                    await sent_message.edit(embed=self.channel_update)
                await asyncio.sleep(1)
            except asyncio.CancelledError:
                return

    @tasks.loop(seconds=1800, count=None)
    async def update_motw(self):
        monkey_guild: discord.Guild = self.bot.get_guild(config.monkey_guild_id)
        motw_role = monkey_guild.get_role(config.motw_role_id)
        motw_channel: discord.TextChannel = self.bot.get_channel(config.motw_channel_id)
        results = await self.bot.loop.run_in_executor(None, partial(self.database.get_last_week_messages, monkey_guild))
        members = [monkey_guild.get_member(user[0]) for user in results]
        for member in monkey_guild.members:
            if motw_role in member.roles and member not in members:
                await member.remove_roles(motw_role)
                await motw_channel.send(f"Goodbye {member.mention}! You will be missed!")
        for member in members:
            if motw_role not in member.roles:
                await member.add_roles(motw_role)
                await motw_channel.send(f"Welcome {member.mention}! I hope you enjoy your stay!")

    @commands.command()
    async def score(self, ctx, member: Optional[discord.Member]):
        if member is None:
            member = ctx.author
        score = await self.bot.loop.run_in_executor(None, partial(self.database.get_last_week_score, member))
        embed = self.bot.create_completed_embed(f"Score for {member.nick or member.name} - past 7 days",
                                                str(score))
        embed.set_footer(text="More information about this in #role-assign (monkeys of the week!)")
        await ctx.reply(embed=embed)

    @commands.command()
    @is_owner()
    async def channel_backwards(self, ctx):
        channel = ctx.channel
        last_edit = time.time()
        resume_from = self.data.get("resume_before_{}".format(channel.id), None)
        sent_message = await ctx.reply(embed=self.bot.create_processing_embed("Working...", "Starting processing!"))
        task = self.bot.loop.create_task(self.send_channel_update(sent_message))
        if resume_from is not None:
            resume_from = await channel.fetch_message(resume_from)
        # noinspection DuplicatedCode
        with ThreadPoolExecutor() as executor:
            async for message in channel.history(limit=None, oldest_first=False, before=resume_from):
                now = time.time()
                if now - last_edit > 5:
                    embed = discord.Embed(title="Processing messages",
                                          description="Last Message text: {}, from {}, in {}".format(
                                              message.clean_content, message.created_at.strftime("%Y-%m-%d %H:%M"),
                                              channel.mention), colour=discord.Colour.orange())
                    embed.set_author(name=message.author.name, icon_url=message.author.avatar_url)
                    embed.timestamp = message.created_at
                    self.channel_update = embed
                    last_edit = now
                    self.data[f"resume_before_{channel.id}"] = message.id
                executor.submit(partial(self.database.save_message, message))
        task.cancel()

    @commands.command()
    @is_owner()
    async def full_guild(self, ctx):
        sent_message = await ctx.reply(embed=self.bot.create_processing_embed("Working...", "Starting processing!"))
        tasks = []
        for channel in ctx.guild.text_channels:
            tasks.append(self.bot.loop.create_task(self.load_channel(channel)))
        while any([not task.done() for task in tasks]):
            await self.send_update(sent_message)
            await asyncio.sleep(1)
        await asyncio.gather(*tasks)
        await sent_message.edit(embed=self.bot.create_completed_embed("Finished", "done ALL messages. wow."))

    async def load_channel(self, channel: discord.TextChannel):
        last_edit = time.time()
        resume_from = self.data.get("resume_from_{}".format(channel.id), None)
        if resume_from is not None:
            resume_from = await channel.fetch_message(resume_from)
        print(resume_from)
        # noinspection DuplicatedCode
        with ThreadPoolExecutor() as executor:
            async for message in channel.history(limit=None, oldest_first=True, after=resume_from):
                now = time.time()
                if now - last_edit > 3:
                    embed = discord.Embed(title="Processing messages",
                                          description="Last Message text: {}, from {}, in {}".format(
                                              message.clean_content, message.created_at.strftime("%Y-%m-%d %H:%M"),
                                              channel.mention), colour=discord.Colour.orange())
                    embed.set_author(name=message.author.name, icon_url=message.author.avatar_url)
                    embed.timestamp = message.created_at
                    self.last_update = embed
                    last_edit = now
                    self.data[f"resume_from_{channel.id}"] = message.id
                executor.submit(partial(self.database.save_message, message))

    @commands.command()
    async def leaderboard(self, ctx):
        guild = ctx.guild
        results = await self.bot.loop.run_in_executor(None, partial(self.database.get_last_week_messages, guild))
        embed = discord.Embed(title="Activity Leaderboard - Past 7 Days", colour=discord.Colour.green())
        embed.description = "```"
        embed.set_footer(text="More information about this in #role-assign (monkeys of the week!)")
        regex_pattern = re.compile(pattern="["
                                           u"\U0001F600-\U0001F64F"
                                           u"\U0001F300-\U0001F5FF"
                                           u"\U0001F680-\U0001F6FF"
                                           u"\U0001F1E0-\U0001F1FF"
                                           "]+", flags=re.UNICODE)
        lengthening = []
        for index, user in enumerate(results):
            member = guild.get_member(user[0])
            name = (member.nick or member.name).replace("✨", "aa")
            name = regex_pattern.sub('a', name)
            name_length = len(name)
            lengthening.append(name_length + len(str(index + 1)))
        max_length = max(lengthening)
        for i in range(len(results)):
            member = guild.get_member(results[i][0])
            name = member.nick or member.name
            text = f"{i + 1}. {name}: " + " " * (max_length - lengthening[i]) + f"Score: {results[i][1]}\n"
            embed.description += text
            # embed.add_field(name=f"{index+1}. {name}", value=f"Score: {user[1]} | Messages: {user[2]}", inline=False)
        embed.description += "```"
        await ctx.reply(embed=embed)

    @commands.command()
    async def stats(self, ctx, member: Optional[discord.Member], group: Optional[str] = "m"):
        group = group.lower()
        if member is None:
            member = ctx.author
        if group not in ['d', 'w', 'm', 'y']:
            await ctx.reply(embed=self.bot.create_error_embed("Valid grouping options are d, w, m, y"))
            return
        times = await self.bot.loop.run_in_executor(None, partial(self.database.get_graph_of_messages, member))
        with ProcessPoolExecutor() as pool:
            file = await self.bot.loop.run_in_executor(pool, partial(self.database.file_from_timestamps, times, group))
        discord_file = discord.File(fp=file, filename="image.png")
        await ctx.reply(file=discord_file)

    @commands.command()
    async def snipe(self, ctx):
        channel = ctx.channel
        message = await self.bot.loop.run_in_executor(None, partial(self.database.snipe, channel))
        user = self.bot.get_user(message.user_id)
        embed = discord.Embed(title="Sniped Message", colour=discord.Colour.red())
        embed.set_author(name=user.name, icon_url=user.avatar_url)
        embed.description = message.content
        embed.timestamp = message.timestamp
        await ctx.reply(embed=embed)

    @commands.Cog.listener()
    async def on_member_update(self, _, after):
        await self.bot.loop.run_in_executor(None, partial(self.database.update_member, after))

    @commands.Cog.listener()
    async def on_member_join(self, member):
        await self.bot.loop.run_in_executor(None, partial(self.database.update_member, member))

    @commands.Cog.listener()
    async def on_member_remove(self, member):
        await self.bot.loop.run_in_executor(None, partial(self.database.delete_member, member))

    @commands.Cog.listener()
    async def on_message(self, message):
        await self.bot.loop.run_in_executor(None, partial(self.database.save_message, message))

    @commands.Cog.listener()
    async def on_raw_message_edit(self, payload: discord.RawMessageUpdateEvent):
        message_edit = await self.bot.loop.run_in_executor(None, partial(self.database.save_message_edit_raw, payload))
        await asyncio.sleep(2)
        if message_edit is None:
            channel: discord.TextChannel = self.bot.get_channel(payload.channel_id)
            message = await channel.fetch_message(payload.message_id)
            await self.bot.loop.run_in_executor(None, partial(self.database.save_message_edit, message))

    @commands.Cog.listener()
    async def on_raw_message_delete(self, payload):
        await self.bot.loop.run_in_executor(None, partial(self.database.mark_deleted, payload.message_id))

    @commands.Cog.listener()
    async def on_bulk_message_delete(self, messages):
        for message in messages:
            await self.bot.loop.run_in_executor(None, partial(self.database.mark_deleted, message.id))

    @commands.Cog.listener()
    async def on_guild_channel_update(self, _, after):
        if isinstance(after, discord.TextChannel):
            await self.bot.loop.run_in_executor(None, partial(self.database.channel_updated, after))

    @commands.Cog.listener()
    async def on_guild_channel_delete(self, channel):
        if isinstance(channel, discord.TextChannel):
            await self.bot.loop.run_in_executor(None, partial(self.database.delete_channel, channel))

    @commands.Cog.listener()
    async def on_guild_channel_create(self, channel):
        if isinstance(channel, discord.TextChannel):
            await self.bot.loop.run_in_executor(None, partial(self.database.channel_updated, channel))

    @commands.Cog.listener()
    async def on_guild_join(self, guild):
        await self.bot.loop.run_in_executor(None, partial(self.database.add_guild, guild))

    @commands.Cog.listener()
    async def on_guild_update(self, _, guild):
        await self.bot.loop.run_in_executor(None, partial(self.database.add_guild, guild))

    @commands.Cog.listener()
    async def on_guild_remove(self, guild):
        await self.bot.loop.run_in_executor(None, partial(self.database.remove_guild, guild))

    @commands.Cog.listener()
    async def on_guild_role_create(self, role):
        await self.bot.loop.run_in_executor(None, partial(self.database.add_role, role))

    @commands.Cog.listener()
    async def on_guild_role_update(self, _, role):
        await self.bot.loop.run_in_executor(None, partial(self.database.add_role, role))

    @commands.Cog.listener()
    async def on_guild_role_delete(self, role):
        await self.bot.loop.run_in_executor(None, partial(self.database.remove_role, role))


def setup(bot: UtilsBot):
    cog = SQLAlchemyTest(bot)
    bot.add_cog(cog)
