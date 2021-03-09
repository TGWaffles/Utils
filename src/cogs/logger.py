import asyncio
import re
import base64
import time
import datetime
import json
import os
from io import BytesIO
from concurrent.futures import ThreadPoolExecutor, ProcessPoolExecutor
from functools import partial
from typing import Optional
from aiohttp import web

import discord
import src.storage.config as config
from src.storage.token import api_token
from discord.ext import commands, tasks

from main import UtilsBot
from src.checks.user_check import is_owner
from src.helpers.sqlalchemy_helper import DatabaseHelper
from src.helpers.storage_helper import DataHelper
from src.helpers.graph_helper import file_from_timestamps, pie_chart_from_amount_and_labels


class SQLAlchemyTest(commands.Cog):
    def __init__(self, bot: UtilsBot):
        self.bot = bot
        self.database = DatabaseHelper()
        self.bot.loop.run_in_executor(None, self.database.ensure_db)
        self.last_update = self.bot.create_processing_embed("Working...", "Starting processing!")
        self.channel_update = self.bot.create_processing_embed("Working...", "Starting processing!")
        self.data = DataHelper()
        self.update_message_count.start()
        app = web.Application()
        app.add_routes([web.get('/ping', self.check_up), web.post("/restart", self.nice_restart),
                        web.get("/someone", self.send_random_someone), web.get("/snipe", self.snipe),
                        web.get("/global_phrase_count", self.count), web.get("/leaderboard", self.leaderboard),
                        web.get("/percentage", self.percentage), web.get("/leaderboard_pie", self.get_leaderboard_pie),
                        web.post("/many_messages", self.add_messages)])
        os.system("tmux new -d -s MonkeyWatch sh start_watch.sh")
        # noinspection PyProtectedMember
        self.bot.loop.create_task(web._run_app(app, port=6970))

    @tasks.loop(seconds=600, count=None)
    async def update_message_count(self):
        count_channel: discord.TextChannel = self.bot.get_channel(config.message_count_channel)
        count = await self.bot.loop.run_in_executor(None, partial(self.database.all_messages, count_channel.guild.id))
        await count_channel.edit(name=f"Messages: {count:,}")

    @staticmethod
    async def check_up(request: web.Request):
        try:
            request_json = await request.json()
            if request_json.get("timestamp", None) is None:
                raise TypeError
        except (TypeError, json.JSONDecodeError):
            return web.Response(status=400)
        sent_time = request_json.get("timestamp")
        current_time = datetime.datetime.utcnow().timestamp()
        response_json = {"time_delay": current_time - sent_time}
        return web.json_response(response_json)

    async def nice_restart(self, request: web.Request):
        try:
            request_json = await request.json()
            assert request_json.get("token", "") == api_token
        except (TypeError, json.JSONDecodeError):
            return web.Response(status=400)
        except AssertionError:
            return web.Response(status=401)
        response = web.StreamResponse(status=202)
        await response.prepare(request)
        self.bot.restart()

    async def send_random_someone(self, request: web.Request):
        try:
            request_json = await request.json()
            assert request_json.get("token", "") == api_token
        except (TypeError, json.JSONDecodeError):
            return web.Response(status=400)
        except AssertionError:
            return web.Response(status=401)
        guild_id = request_json.get("guild_id", None)
        if guild_id is None:
            return web.Response(status=400)
        random_id = await self.bot.loop.run_in_executor(None, partial(self.database.select_random,
                                                                      guild_id))
        response_json = {"member_id": random_id}
        return web.json_response(response_json)

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

    async def leaderboard(self, request: web.Request):
        try:
            request_json = await request.json()
            assert request_json.get("token", "") == api_token
        except (TypeError, json.JSONDecodeError):
            return web.Response(status=400)
        except AssertionError:
            return web.Response(status=401)
        guild_id = request_json.get("guild_id", None)
        if guild_id is None:
            return web.Response(status=400)
        results = await self.bot.loop.run_in_executor(None, partial(self.database.get_last_week_messages, guild_id))
        response_json = {"results": results[:12]}
        return web.json_response(response_json)

    async def get_leaderboard_pie(self, request: web.Request):
        try:
            request_json = await request.json()
            assert request_json.get("token", "") == api_token
        except (TypeError, json.JSONDecodeError):
            return web.Response(status=400)
        except AssertionError:
            return web.Response(status=401)
        guild_id = request_json.get("guild_id", None)
        if guild_id is None:
            return web.Response(status=400)
        results = await self.bot.loop.run_in_executor(None, partial(self.database.get_last_week_messages, guild_id))
        labels = []
        amounts = []
        for user_id, score in results:
            labels.append(self.bot.get_user(user_id).name)
            amounts.append(score)
        smaller_amounts = amounts[15:]
        labels = labels[:15]
        amounts = amounts[:15]
        amounts.append(sum(smaller_amounts))
        labels.append("Other")
        response_json = {"labels": labels, "amounts": amounts}
        return web.json_response(response_json)

    @commands.command()
    async def stats(self, ctx, member: Optional[discord.Member], group: Optional[str] = "m"):
        group = group.lower()
        if member is None:
            member = ctx.author
        if group not in ['d', 'w', 'm', 'y']:
            await ctx.reply(embed=self.bot.create_error_embed("Valid grouping options are d, w, m, y"))
            return
        english_group = {'d': "Day", 'w': "Week", 'm': "Month", 'y': "Year"}
        sent = await ctx.reply(embed=self.bot.create_processing_embed("Processing messages", "Compiling graph for all "
                                                                                             "your messages..."))
        times = await self.bot.loop.run_in_executor(None, partial(self.database.get_graph_of_messages, member))
        with ProcessPoolExecutor() as pool:
            data = await self.bot.loop.run_in_executor(pool, partial(file_from_timestamps, times, group))
        file = BytesIO(data)
        file.seek(0)
        discord_file = discord.File(fp=file, filename="image.png")
        embed = discord.Embed(title=f"Your stats for this {english_group[group]}:")
        embed.set_image(url="attachment://image.png")
        await sent.delete()
        await ctx.reply(embed=embed, file=discord_file)

    async def percentage(self, request: web.Request):
        try:
            request_json = await request.json()
            assert request_json.get("token", "") == api_token
        except (TypeError, json.JSONDecodeError):
            return web.Response(status=400)
        except AssertionError:
            return web.Response(status=401)
        guild_id = request_json.get("guild_id", None)
        member_id = request_json.get("member_id", None)
        if guild_id is None or member_id is None:
            return web.Response(status=400)
        amount, percentage = await self.bot.loop.run_in_executor(None, partial(self.database.count_messages,
                                                                               member_id, guild_id))
        response_json = {"amount": amount, "percentage": percentage}
        return web.json_response(response_json)

    async def snipe(self, request: web.Request):
        try:
            request_json = await request.json()
            assert request_json.get("token", "") == api_token
        except (TypeError, json.JSONDecodeError):
            return web.Response(status=400)
        except AssertionError:
            return web.Response(status=401)
        channel_id = request_json.get("channel_id", None)
        amount = request_json.get("amount", 1)
        if channel_id is None:
            return web.Response(status=400)
        message = await self.bot.loop.run_in_executor(None, partial(self.database.snipe, channel_id, amount))
        response_json = {"user_id": message.user_id, "content": message.content, "timestamp":
                         message.timestamp.isoformat("T")}
        return web.json_response(response_json)

    async def add_messages(self, request: web.Request):
        try:
            request_json = await request.json()
            assert request_json.get("token", "") == api_token
        except (TypeError, json.JSONDecodeError):
            return web.Response(status=400)
        except AssertionError:
            return web.Response(status=401)
        messages = request_json.get("messages", [])
        await self.bot.loop.run_in_executor(None, partial(self.database.add_many_messages, *messages))
        return web.json_response({"success": True})

    async def count(self, request: web.Request):
        try:
            request_json = await request.json()
            assert request_json.get("token", "") == api_token
        except (TypeError, json.JSONDecodeError):
            return web.Response(status=400)
        except AssertionError:
            return web.Response(status=401)
        phrase = request_json.get("phrase", None)
        guild_id = request_json.get("guild_id", None)
        if phrase is None or guild_id is None:
            return web.Response(status=400)
        amount = await self.bot.loop.run_in_executor(None, partial(self.database.count, guild_id, phrase))
        response_json = {"amount": amount}
        return web.json_response(response_json)

    @commands.command(description="Count how many times a user has said a phrase!", aliases=["countuser", "usercount"])
    async def count_user(self, ctx, member: Optional[discord.Member], *, phrase):
        if member is None:
            member = ctx.author
        if len(phrase) > 180:
            await ctx.reply(embed=self.bot.create_error_embed("That phrase was too long!"))
            return
        sent = await ctx.reply(embed=self.bot.create_processing_embed("Counting...",
                                                                      f"Counting how many times {member.display_name} "
                                                                      f"said: \"{phrase}\""))
        amount = await self.bot.loop.run_in_executor(None, partial(self.database.count_member, member, phrase))
        embed = self.bot.create_completed_embed(
            f"Number of times {member.display_name} said: \"{phrase}\":", f"**{amount}** times!")
        embed.set_footer(text="If you entered a phrase, remember to surround it in **straight** quotes (\"\")!")
        await sent.edit(embed=embed)

    @commands.command(description="Plots a bar chart of word usage over time.", aliases=["wordstats, wordusage",
                                                                                         "word_stats", "phrase_usage",
                                                                                         "phrasestats", "phrase_stats",
                                                                                         "phraseusage"])
    async def word_usage(self, ctx, phrase, group: Optional[str] = "m"):
        async with ctx.typing():
            if len(phrase) > 180:
                await ctx.reply(embed=self.bot.create_error_embed("That phrase was too long!"))
                return
            print("Getting phrase times.")
            times = await self.bot.loop.run_in_executor(None, partial(self.database.phrase_times, ctx.guild, phrase))
            print("Running process")
            with ProcessPoolExecutor() as pool:
                data = await self.bot.loop.run_in_executor(pool, partial(file_from_timestamps, times, group))
            print("Finished processing.")
            file = BytesIO(data)
            file.seek(0)
            discord_file = discord.File(fp=file, filename="image.png")
            embed = discord.Embed(title=f"Number of times \"{phrase}\" has been said:")
            embed.set_image(url="attachment://image.png")
            print("Compiled embed")
            await ctx.reply(embed=embed, file=discord_file)
            print("Embed sent.")

    @commands.command(description="Count how many messages have been sent in this guild!")
    async def messages(self, ctx):
        sent = await ctx.reply(embed=self.bot.create_processing_embed("Counting...", "Counting all messages sent..."))
        amount = await self.bot.loop.run_in_executor(None, partial(self.database.all_messages, ctx.guild.id))
        await sent.edit(embed=self.bot.create_completed_embed(
            title="Total Messages sent in this guild!", text=f"**{amount:,}** messages!"
        ))

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
