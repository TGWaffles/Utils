import asyncio
import concurrent.futures
import datetime
import time
from functools import partial
from io import BytesIO
from typing import Optional, Any, Dict

import aiohttp
import aiohttp.client_exceptions
import unidecode
import base64
from discord.ext import commands, tasks

from main import UtilsBot
from src.checks.custom_check import restart_check
from src.checks.user_check import is_owner
from src.checks.role_check import is_high_staff, is_staff
from src.helpers.graph_helper import pie_chart_from_amount_and_labels
from src.helpers.storage_helper import DataHelper
from src.helpers.api_helper import *
from src.storage import config
from src.storage.token import api_token

exceptions = (asyncio.exceptions.TimeoutError, aiohttp.client_exceptions.ServerDisconnectedError,
              aiohttp.client_exceptions.ClientConnectorError)
waiting_exceptions = (aiohttp.client_exceptions.ClientOSError, aiohttp.client_exceptions.ContentTypeError)
default_timeout = 45


class DBApiClient(commands.Cog):
    def __init__(self, bot: UtilsBot):
        self.bot = bot
        self.bot.database_handler = self
        self.session = aiohttp.ClientSession()
        self.restarting = False
        self.data = DataHelper()
        self.db_url = "elastic.thom.club"
        self.bot.loop.create_task(self.ping_db_server())
        self.last_update = self.bot.create_processing_embed("Working...", "Starting processing!")
        self.last_ping = datetime.datetime.now()
        self.active_channel_ids = []
        self.channel_lock = asyncio.Lock()
        self.update_motw.start()

    async def send_request(self, endpoint, parameters, request_type="get", timeout=default_timeout) -> Dict[Any, Any]:
        attempts = 0
        last_status = -1
        while True:
            if attempts > 10:
                return {"failure": True, "status": last_status}
            try:
                if request_type == "get":
                    request = await self.session.get(f"http://{self.db_url}:{config.port}/{endpoint}", timeout=timeout,
                                                     json=parameters)
                else:
                    request = await self.session.post(f"http://{self.db_url}:{config.port}/{endpoint}", timeout=timeout,
                                                      json=parameters)
                if request.status != 200:
                    last_status = request.status
                    attempts += 1
                    await asyncio.sleep(0.5)
                    continue
                response_json = await request.json()
                return response_json
            except exceptions:
                await self.restart_db_server()
                attempts += 1
            except waiting_exceptions:
                await asyncio.sleep(1)
                attempts += 1
            await asyncio.sleep(0.5)

    @tasks.loop(seconds=1800, count=None)
    async def update_motw(self):
        monkey_guild: discord.Guild = self.bot.get_guild(config.monkey_guild_id)
        motw_role = monkey_guild.get_role(config.motw_role_id)
        motw_channel: discord.TextChannel = self.bot.get_channel(config.motw_channel_id)
        params = {'token': api_token, 'guild_id': config.monkey_guild_id}
        try:
            async with self.session.get(url=f"http://{self.db_url}:{config.port}/leaderboard", timeout=30,
                                        json=params) as request:
                response_json = await request.json()
                results = response_json.get("results")
        except exceptions:
            await self.restart_db_server()
            return
        except waiting_exceptions:
            return
        members = []
        for user in results:
            member = monkey_guild.get_member(user[0])
            if member is None:
                await self.request_member_remove(user[0], monkey_guild.id)
                continue
            members.append(member)
        for member in monkey_guild.members:
            if motw_role in member.roles and member not in members:
                await member.remove_roles(motw_role)
                await motw_channel.send(f"Goodbye {member.mention}! You will be missed!")
        for member in members:
            if motw_role not in member.roles:
                await member.add_roles(motw_role)
                await motw_channel.send(f"Welcome {member.mention}! I hope you enjoy your stay!")

    async def ping_db_server(self):
        while True:
            try:
                params = {'timestamp': datetime.datetime.utcnow().timestamp()}
                async with self.session.get(url=f"http://{self.db_url}:{config.port}/ping", timeout=5,
                                            json=params) as request:
                    json_info = await request.json()
                    self.last_ping = datetime.datetime.now()
                    if json_info.get("time_delay", 100) > 3:
                        self.bot.loop.create_task(self.restart_db_server())
                        await asyncio.sleep(3)
            except exceptions:
                self.bot.loop.create_task(self.restart_db_server())
                await asyncio.sleep(5)
            except waiting_exceptions:
                await asyncio.sleep(2)
            await asyncio.sleep(1)

    async def restart_db_server(self):
        if not self.restarting:
            try:
                params = {'token': api_token}
                self.restarting = True
                try:
                    async with self.session.post(url=f"http://{self.db_url}:{config.port}/restart", timeout=60,
                                                 json=params) as request:
                        if request.status == 202:
                            print("Restarted DB server")
                        else:
                            raise aiohttp.client_exceptions.ClientConnectorError
                except (aiohttp.client_exceptions.ClientConnectorError, *exceptions):
                    while True:
                        try:
                            await self.session.post(url=f"http://{self.db_url}:{config.restart_port}/restart",
                                                    json=params)
                            break
                        except exceptions:
                            await asyncio.sleep(0.5)
                            print("Failed to force a restart. trying again.")
                    print("Force restarted DB server due to error in normal restart.")
                except waiting_exceptions:
                    self.restarting = False
                    await self.restart_db_server()
                last_ping = self.last_ping
                seconds_waited = 0
                while self.last_ping == last_ping:
                    if seconds_waited > 30:
                        await self.session.post(url=f"http://{self.db_url}:{config.restart_port}/restart", json=params)
                        print("Force restarted DB server due to ping not working..")
                        seconds_waited = 0
                    seconds_waited += 0.1
                    await asyncio.sleep(0.1)
            finally:
                self.restarting = False

    async def get_someone_id(self, guild_id):
        params = {'token': api_token, "guild_id": guild_id}
        response_json = await self.send_request("someone", parameters=params)
        if response_json is None:
            return None
        return response_json.get("member_id")

    @commands.command()
    async def snipe(self, ctx, amount=1):
        sent = await ctx.reply(embed=self.bot.create_processing_embed("Processing...", "Getting sniped message..."))
        params = {'token': api_token, 'channel_id': ctx.channel.id, "amount": amount}
        response_json = await self.send_request("snipe", parameters=params)
        if response_json.get("failure", False):
            await sent.edit(embed=self.bot.create_error_embed(f"Couldn't snipe!"
                                                              f"Status: {response_json.get('status')}"))
            return
        user_id = response_json.get("user_id")
        content = response_json.get("content")
        embed_json = response_json.get("embed_json")
        timestamp = datetime.datetime.fromisoformat(response_json.get("timestamp"))
        user = self.bot.get_user(user_id)
        if user is None:
            user = await self.bot.fetch_user(user_id)
        embed = discord.Embed(title="Sniped Message", colour=discord.Colour.red())
        embed.set_author(name=user.name, icon_url=user.avatar_url)
        preceding_message = (await ctx.channel.history(before=timestamp, limit=1).flatten())[0] or None
        if embed_json is None:
            embed.description = content
        else:
            embed = discord.Embed.from_dict(embed_json)
            if len(embed.fields) == 0 or not embed.fields[0].name.startswith("Previous Title"):
                embed.insert_field_at(0, name="Previous Title", value=embed.title, inline=False)
            embed.title = "Sniped Message!"
        if preceding_message is not None:
            embed.add_field(name="\u200b", value=f"[Previous Message]({preceding_message.jump_url})",
                            inline=False)
        embed.timestamp = timestamp
        await sent.edit(embed=embed)

    @commands.command()
    async def edits(self, ctx):
        if ctx.message.reference is None:
            await ctx.reply(embed=self.bot.create_error_embed("Please reply to a message with this command!"))
            return
        referenced_message = ctx.message.reference
        sent = await ctx.reply(embed=self.bot.create_processing_embed("Processing...", "Getting message edits..."))
        params = {'token': api_token, 'message_id': referenced_message.message_id}
        response_json = await self.send_request("edits", parameters=params)
        if response_json.get("failure", False):
            await sent.edit(embed=self.bot.create_error_embed(f"Couldn't fetch edits! "
                                                              f"Status: {response_json.get('status')}"))
            return
        edits = response_json.get("edits")
        original_message = response_json.get("original")
        original_timestamp_string = datetime.datetime.fromisoformat(
            original_message.get("timestamp")).strftime("%Y-%m-%d %H:%M:%S")
        if len(edits) == 0:
            await sent.edit(embed=self.bot.create_error_embed("That message has no known edits."))
            return
        embed = discord.Embed(title="Edits for Message", colour=discord.Colour.gold())
        if len(original_message.get("content")) > 1024:
            content = original_message.get("content")[:1021] + "..."
        else:
            content = original_message.get("content")
        embed.add_field(name=f"Original Message ({original_timestamp_string})",
                        value=content, inline=False)
        for index, edit in enumerate(edits):
            if len(embed) >= 5000:
                break
            edited_timestamp_string = datetime.datetime.fromisoformat(
                edit.get("timestamp")).strftime("%Y-%m-%d %H:%M:%S")
            if len(edit.get("edited_content")) > 1024:
                content = edit.get("edited_content")[:1021] + "..."
            else:
                content = edit.get("edited_content")
            embed.insert_field_at(index=1, name=f"Edit {len(edits) - index} ({edited_timestamp_string})",
                                  value=content, inline=False)
        if referenced_message.resolved is not None:
            author = referenced_message.resolved.author
            embed.set_author(name=author.name, url=author.avatar_url)
        embed.add_field(name="\u200b", value=f"[Jump to Message]({referenced_message.jump_url})",
                        inline=False)
        await sent.edit(embed=embed)

    @commands.command(description="Get leaderboard pie!")
    async def leaderpie(self, ctx):
        sent = await ctx.reply(embed=self.bot.create_processing_embed("Generating leaderboard",
                                                                      "Processing messages for leaderboard..."))
        params = {'token': api_token, 'guild_id': ctx.guild.id}
        response_json = await self.send_request("leaderboard_pie", parameters=params)
        if response_json.get("failure", False):
            await sent.edit(embed=self.bot.create_error_embed(f"Couldn't generate leaderboard! "
                                                              f"Status: {response_json.get('status')}"))
            return
        labels = response_json.get("labels")
        amounts = response_json.get("amounts")
        await sent.edit(embed=self.bot.create_processing_embed("Got leaderboard!", "Generating pie chart."))
        with concurrent.futures.ProcessPoolExecutor() as pool:
            data = await self.bot.loop.run_in_executor(pool, partial(pie_chart_from_amount_and_labels,
                                                                     labels, amounts))
        file = BytesIO(data)
        file.seek(0)
        discord_file = discord.File(fp=file, filename="image.png")
        await ctx.reply(file=discord_file)
        await sent.delete()

    @commands.command(description="Count how many times a phrase has been said!")
    async def count(self, ctx, *, phrase):
        if len(phrase) > 223:
            await ctx.reply(embed=self.bot.create_error_embed("That phrase was too long!"))
            return
        sent = await ctx.reply(embed=self.bot.create_processing_embed("Counting...",
                                                                      f"Counting how many times \"{phrase}\" "
                                                                      f"has been said..."))
        params = {"phrase": phrase, "guild_id": ctx.guild.id, "token": api_token}
        response_json = await self.send_request("global_phrase_count", parameters=params)
        if response_json.get("failure", False):
            await sent.edit(embed=self.bot.create_error_embed(f"Couldn't count! "
                                                              f"Status: {response_json.get('status')}"))
            return
        amount = response_json.get("amount")
        embed = self.bot.create_completed_embed(
            f"Number of times \"{phrase}\" has been said:", f"**{amount}** times!")
        embed.set_footer(text="If you entered a phrase, remember to surround it in **straight** quotes ("
                              "\"\")!")
        await sent.edit(embed=embed)

    @commands.command(aliases=["ratio", "percentage"])
    async def percent(self, ctx, member: Optional[discord.User]):
        if member is None:
            member = ctx.author
        sent = await ctx.reply(embed=self.bot.create_processing_embed("Counting...",
                                                                      f"Counting {member.name}'s amount of "
                                                                      f"messages!"))
        params = {"guild_id": ctx.guild.id, "member_id": member.id, "token": api_token}
        response_json = await self.send_request("percentage", parameters=params)
        if response_json.get("failure", False):
            await sent.edit(embed=self.bot.create_error_embed(f"Couldn't count! "
                                                              f"Status: {response_json.get('status')}"))
            return
        amount = response_json.get("amount")
        percentage = response_json.get("percentage")
        embed = self.bot.create_completed_embed(f"Amount of messages {member.name} has sent!",
                                                f"{member.name} has sent {amount:,} messages. "
                                                f"That's {percentage}% "
                                                f"of the server's total!")
        await sent.edit(embed=embed)

    async def send_update(self, sent_message):
        if len(self.last_update.description) < 2000:
            await sent_message.edit(embed=self.last_update)

    @commands.command()
    @restart_check()
    async def full_guild(self, ctx, reset=False):
        sent_message = await ctx.reply(embed=self.bot.create_processing_embed("Working...", "Starting processing!"))
        tasks = []
        for channel in ctx.guild.text_channels:
            tasks.append(self.bot.loop.create_task(self.load_channel(channel, reset)))
        while any([not task.done() for task in tasks]):
            await self.send_update(sent_message)
            await asyncio.sleep(1)
        await asyncio.gather(*tasks)
        await sent_message.edit(embed=self.bot.create_completed_embed("Finished", "done ALL messages. wow."))

    @commands.command()
    @is_owner()
    async def all_guilds(self, ctx):
        sent_message = await ctx.reply(embed=self.bot.create_processing_embed("Working...", "Starting processing!"))
        tasks = []
        channels_to_do = []
        for guild in self.bot.guilds:
            print(guild.name)
            for channel in guild.text_channels:
                print(channel.name)
                channels_to_do.append(channel)
        for i in range(10):
            channel = channels_to_do.pop()
            tasks.append(self.bot.loop.create_task(self.load_channel(channel, True)))
        await asyncio.sleep(3)
        while len(self.active_channel_ids) > 0:
            if len(self.active_channel_ids) < 10:
                print(len(self.active_channel_ids))
                print(self.active_channel_ids)
                channel = channels_to_do.pop()
                print(f"Adding channel id {channel}")
                tasks.append(self.bot.loop.create_task(self.load_channel(channel, True)))
            await self.send_update(sent_message)
            await asyncio.sleep(1)
        print("done??")
        print(self.active_channel_ids)
        await asyncio.gather(*tasks)
        await sent_message.edit(embed=self.bot.create_completed_embed("Finished", "done ALL messages. wow."))

    async def load_channel(self, channel, reset):
        print(channel.name)
        last_edit = time.time()
        resume_from = self.data.get("resume_from_{}".format(channel.id), None)
        if reset:
            resume_from = None
        if resume_from is not None:
            resume_from = await channel.fetch_message(resume_from)
        messages_to_send = []
        # noinspection DuplicatedCode
        async for message in channel.history(limit=None, oldest_first=True, after=resume_from):
            now = time.time()
            if now - last_edit > 3:
                embed = discord.Embed(title="Processing messages",
                                      description="Last Message text: {}, from {}, in {}, in {}".format(
                                          message.clean_content, message.created_at.strftime("%Y-%m-%d %H:%M"),
                                          channel.name, channel.guild.name), colour=discord.Colour.orange())
                embed.set_author(name=message.author.name, icon_url=message.author.avatar_url)
                embed.timestamp = message.created_at
                self.last_update = embed
                last_edit = now
                self.data[f"resume_from_{channel.id}"] = message.id
            if len(message.embeds) > 0:
                embed_json = message.embeds[0].to_dict()
            else:
                embed_json = None
            messages_to_send.append({"id": message.id, "channel_id": message.channel.id,
                                     "guild_id": message.guild.id, "user_id": message.author.id,
                                     "content": message.content, "embed_json": embed_json,
                                     "timestamp": message.created_at.isoformat(), "name": message.author.name,
                                     "bot": message.author.bot, "channel_name": message.channel.name})
            if len(messages_to_send) >= 100:
                await self.send_request("many_messages", parameters={"token": api_token,
                                                                     "messages": messages_to_send},
                                        request_type="post")

    @commands.command()
    async def leaderboard(self, ctx):
        sent = await ctx.reply(embed=self.bot.create_processing_embed("Generating leaderboard",
                                                                      "Processing messages for leaderboard..."))
        params = {'token': api_token, 'guild_id': ctx.guild.id}
        response_json = await self.send_request("leaderboard", parameters=params)
        if response_json.get("failure", False):
            await sent.edit(embed=self.bot.create_error_embed(f"Couldn't generate leaderboard!"
                                                              f"Status: {response_json.get('status')}"))
            return
        results = response_json.get("results")
        embed = discord.Embed(title="Activity Leaderboard - Past 7 Days", colour=discord.Colour.green())
        embed.description = "```"
        embed.set_footer(text="More information about this in #role-assign (monkeys of the week!)")
        lengthening = []
        for index, user in enumerate(results):
            name = await self.name_from_id(user[0], ctx.guild)
            name = unidecode.unidecode(name)
            name_length = len(name)
            lengthening.append(name_length + len(str(index + 1)))
        max_length = max(lengthening)
        for i in range(len(results)):
            name = await self.name_from_id(results[i][0], ctx.guild)
            name = unidecode.unidecode(name)
            text = f"{i + 1}. {name}" + " " * (max_length - lengthening[i]) + f" | Score: {results[i][1]}\n"
            embed.description += text
        embed.description += "```"
        await sent.edit(embed=embed)

    @commands.command()
    @is_high_staff()
    async def exclude_channel(self, ctx, channel: Optional[discord.TextChannel]):
        if channel is None:
            channel = ctx.channel
        sent = await ctx.reply(embed=self.bot.create_processing_embed("Excluding channel...",
                                                                      "Sending exclusion request..."))
        params = {'token': api_token, "channel": channel_to_json(channel)}
        response_json = await self.send_request("exclude_channel", parameters=params, request_type="post", timeout=120)
        if response_json.get("failure", False):
            await sent.edit(embed=self.bot.create_error_embed(f"Couldn't exclude channel!"
                                                              f"Status: {response_json.get('status')}"))
            return
        await sent.edit(embed=self.bot.create_completed_embed("Changed excluded status!",
                                                              f"Channel has been "
                                                              f"{'un' if not response_json.get('excluded') else ''}"
                                                              f"excluded!"))

    @commands.command()
    @is_staff()
    async def server_stats(self, ctx, group: Optional[str] = "m"):
        group = group.lower()
        if group not in ['d', 'w', 'm', 'y']:
            await ctx.reply(embed=self.bot.create_error_embed("Valid grouping options are d, w, m, y"))
            return
        english_group = {'d': "Day", 'w': "Week", 'm': "Month", 'y': "Year"}
        sent = await ctx.reply(embed=self.bot.create_processing_embed("Processing messages",
                                                                      "Compiling graph for all "
                                                                      "the server's messages..."))
        params = {'token': api_token, 'guild_id': ctx.guild.id, "group": group}
        response_json = await self.send_request("guild_graph", parameters=params)
        if response_json.get("failure", False) or response_json.get("data") is None:
            await sent.edit(embed=self.bot.create_error_embed(f"Couldn't process stats!"
                                                              f"Status: {response_json.get('status')}"))
            return
        b64_data = response_json.get("data")
        data = base64.b64decode(b64_data)
        file = BytesIO(data)
        file.seek(0)
        discord_file = discord.File(fp=file, filename="image.png")
        embed = discord.Embed(title=f"{ctx.guild.name}'s stats, grouped by {english_group[group]}:")
        embed.set_image(url="attachment://image.png")
        await sent.delete()
        await ctx.reply(embed=embed, file=discord_file)

    async def name_from_id(self, user_id, guild):
        member = guild.get_member(user_id)
        if member is None:
            member = await self.bot.fetch_user(user_id)
            if member is None:
                name = "Unknown Member"
            else:
                name = member.name
        else:
            name = (member.nick or member.name)
        return name

    async def update(self):
        params = {'token': api_token}
        await self.session.post(url=f"http://{self.db_url}:{config.restart_port}/update", json=params)

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.channel.guild is None:
            return
        message_dict = message_to_json(message)
        params = {'token': api_token, 'message': message_dict}
        await self.send_request("on_message", parameters=params, request_type="post", timeout=120)

    @commands.Cog.listener()
    async def on_raw_message_edit(self, payload: discord.RawMessageUpdateEvent):
        payload_data = payload.data
        params = {'token': api_token, 'payload_data': payload_data}
        await self.send_request("on_edit", parameters=params, request_type="post", timeout=120)

    async def request_member_remove(self, member_id, guild_id):
        params = {"token": api_token, "user_id": member_id, "guild_id": guild_id}
        await self.send_request("on_member_remove", parameters=params, request_type="post", timeout=120)

    @commands.Cog.listener()
    async def on_member_remove(self, member: discord.Member):
        await self.request_member_remove(member.id, member.guild.id)

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        pass


def setup(bot: UtilsBot):
    cog = DBApiClient(bot)
    bot.add_cog(cog)
