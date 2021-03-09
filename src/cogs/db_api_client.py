import asyncio
import datetime

import aiohttp
import aiohttp.client_exceptions
import discord
import re
import base64
from io import BytesIO
from discord.ext import commands, tasks
from typing import Optional

from main import UtilsBot
from src.storage.token import api_token
from src.storage import config


exceptions = (asyncio.exceptions.TimeoutError, aiohttp.client_exceptions.ServerDisconnectedError,
              aiohttp.client_exceptions.ClientConnectorError, aiohttp.client_exceptions.ClientOSError)


class DBApiClient(commands.Cog):
    def __init__(self, bot: UtilsBot):
        self.bot = bot
        self.bot.database_handler = self
        self.session = aiohttp.ClientSession()
        self.restarting = False
        self.db_url = "tgwaffles.me"
        self.bot.loop.create_task(self.ping_db_server())
        self.last_ping = datetime.datetime.now()
        self.update_motw.start()

    @tasks.loop(seconds=1800, count=None)
    async def update_motw(self):
        monkey_guild: discord.Guild = self.bot.get_guild(config.monkey_guild_id)
        motw_role = monkey_guild.get_role(config.motw_role_id)
        motw_channel: discord.TextChannel = self.bot.get_channel(config.motw_channel_id)
        params = {'token': api_token, 'guild_id': config.monkey_guild_id}
        try:
            async with self.session.get(url=f"http://{self.db_url}:6970/leaderboard", timeout=10,
                                        json=params) as request:
                response_json = await request.json()
                results = response_json.get("results")
        except exceptions:
            await self.restart_db_server()
            return
        members = [monkey_guild.get_member(user[0]) for user in results]
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
                async with self.session.get(url=f"http://{self.db_url}:6970/ping", timeout=5, json=params) as request:
                    json_info = await request.json()
                    self.last_ping = datetime.datetime.now()
                    if json_info.get("time_delay", 100) > 3:
                        self.bot.loop.create_task(self.restart_db_server())
                        await asyncio.sleep(3)
            except aiohttp.client_exceptions.ClientConnectorError:
                self.bot.loop.create_task(self.restart_db_server())
                await asyncio.sleep(5)
            except asyncio.exceptions.TimeoutError:
                self.bot.loop.create_task(await self.restart_db_server())
                await asyncio.sleep(3)
            await asyncio.sleep(1)

    async def restart_db_server(self):
        if not self.restarting:
            params = {'token': api_token}
            self.restarting = True
            try:
                async with self.session.post(url=f"http://{self.db_url}:6970/restart", timeout=10, json=params) as request:
                    if request.status == 202:
                        print("Restarted DB server")
                    else:
                        raise aiohttp.client_exceptions.ClientConnectorError
            except aiohttp.client_exceptions.ClientConnectorError:
                await self.session.post(url=f"http://{self.db_url}:6969/restart", json=params)
                print("Force restarted DB server.")
            last_ping = self.last_ping
            while self.last_ping == last_ping:
                await asyncio.sleep(0.1)
            self.restarting = False

    async def get_someone_id(self, guild_id):
        params = {'token': api_token, "guild_id": guild_id}
        while True:
            try:
                async with self.session.get(url=f"http://{self.db_url}:6970/someone", timeout=10, json=params) as request:
                    response_json = await request.json()
                    return response_json.get("member_id")
            except exceptions:
                await self.restart_db_server()

    @commands.command()
    async def snipe(self, ctx):
        sent = await ctx.reply(embed=self.bot.create_processing_embed("Processing...", "Getting sniped message..."))
        params = {'token': api_token, 'channel_id': ctx.channel.id}
        while True:
            try:
                async with self.session.get(url=f"http://{self.db_url}:6970/snipe", timeout=10, json=params) as request:
                    if request.status != 200:
                        await sent.edit(embed=self.bot.create_error_embed(f"Couldn't snipe! "
                                                                          f"(status: {request.status})"))
                        return
                    response_json = await request.json()
                    user_id = response_json.get("user_id")
                    content = response_json.get("content")
                    timestamp = datetime.datetime.fromisoformat(response_json.get("timestamp"))
                    user = self.bot.get_user(user_id)
                    embed = discord.Embed(title="Sniped Message", colour=discord.Colour.red())
                    embed.set_author(name=user.name, icon_url=user.avatar_url)
                    preceding_message = (await ctx.channel.history(before=timestamp, limit=1).flatten())[0] or None
                    if preceding_message is not None:
                        embed.add_field(name="\u200b", value=f"[Previous Message]({preceding_message.jump_url})")
                    embed.description = content
                    embed.timestamp = timestamp
                    await sent.edit(embed=embed)
                    return True
            except exceptions:
                await self.restart_db_server()

    @commands.command(description="Get leaderboard pie!")
    async def leaderpie(self, ctx):
        sent = await ctx.reply(embed=self.bot.create_processing_embed("Generating leaderboard",
                                                                      "Processing messages for leaderboard..."))
        params = {'token': api_token, 'guild_id': ctx.guild.id}
        while True:
            try:
                async with self.session.get(url=f"http://{self.db_url}:6970/leaderboard_pie", timeout=10,
                                            json=params) as request:
                    if request.status != 200:
                        await sent.edit(embed=self.bot.create_error_embed(f"Couldn't generate leaderboard! "
                                                                          f"(status: {request.status})"))
                        return
                    request_json = await request.json()
                    data = request_json.get("chart")
                    print(data)
                    file = BytesIO(base64.b64decode(data))
                    file.seek(0)
                    discord_file = discord.File(fp=file, filename="image.jpg")
                    await ctx.reply(file=discord_file)
                    await sent.delete()
                    return
            except exceptions:
                await self.restart_db_server()

    @commands.command(description="Count how many times a phrase has been said!")
    async def count(self, ctx, *, phrase):
        if len(phrase) > 223:
            await ctx.reply(embed=self.bot.create_error_embed("That phrase was too long!"))
            return
        sent = await ctx.reply(embed=self.bot.create_processing_embed("Counting...",
                                                                      f"Counting how many times \"{phrase}\" "
                                                                      f"has been said..."))
        params = {"phrase": phrase, "guild_id": ctx.guild.id, "token": api_token}
        while True:
            try:
                async with self.session.get(url=f"http://{self.db_url}:6970/global_phrase_count", timeout=10,
                                            json=params) as request:
                    if request.status != 200:
                        await sent.edit(embed=self.bot.create_error_embed(f"Couldn't count! "
                                                                          f"(status: {request.status})"))
                        return
                    response_json = await request.json()
                    amount = response_json.get("amount")
                    embed = self.bot.create_completed_embed(
                        f"Number of times \"{phrase}\" has been said:", f"**{amount}** times!")
                    embed.set_footer(text="If you entered a phrase, remember to surround it in **straight** quotes ("
                                          "\"\")!")
                    await sent.edit(embed=embed)
                    return True
            except exceptions:
                await self.restart_db_server()

    @commands.command(aliases=["ratio", "percentage"])
    async def percent(self, ctx, member: Optional[discord.User]):
        if member is None:
            member = ctx.author
        sent = await ctx.reply(embed=self.bot.create_processing_embed("Counting...",
                                                                      f"Counting {member.name}'s amount of "
                                                                      f"messages!"))
        params = {"guild_id": ctx.guild.id, "member_id": member.id, "token": api_token}
        while True:
            try:
                async with self.session.get(url=f"http://{self.db_url}:6970/percentage", timeout=10,
                                            json=params) as request:
                    if request.status != 200:
                        await sent.edit(embed=self.bot.create_error_embed(f"Couldn't count! "
                                                                          f"(status: {request.status})"))
                        return
                    response_json = await request.json()
                    amount = response_json.get("amount")
                    percentage = response_json.get("percentage")
                    embed = self.bot.create_completed_embed(f"Amount of messages {member.name} has sent!",
                                                            f"{member.name} has sent {amount:,} messages. "
                                                            f"That's {percentage}% "
                                                            f"of the server's total!")
                    await sent.edit(embed=embed)
                    return True
            except exceptions:
                await self.restart_db_server()

    @commands.command()
    async def leaderboard(self, ctx):
        sent = await ctx.reply(embed=self.bot.create_processing_embed("Generating leaderboard",
                                                                      "Processing messages for leaderboard..."))
        params = {'token': api_token, 'guild_id': ctx.guild.id}
        while True:
            try:
                async with self.session.get(url=f"http://{self.db_url}:6970/leaderboard", timeout=10,
                                            json=params) as request:
                    if request.status != 200:
                        await sent.edit(embed=self.bot.create_error_embed(f"Couldn't generate leaderboard! "
                                                                          f"(status: {request.status})"))
                        return
                    request_json = await request.json()
                    results = request_json.get("results")
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
                        member = ctx.guild.get_member(user[0])
                        name = (member.nick or member.name).replace("✨", "aa")
                        name = regex_pattern.sub('a', name)
                        name_length = len(name)
                        lengthening.append(name_length + len(str(index + 1)))
                    max_length = max(lengthening)
                    for i in range(len(results)):
                        member = ctx.guild.get_member(results[i][0])
                        name = member.nick or member.name
                        text = f"{i + 1}. {name}: " + " " * (max_length - lengthening[i]) + f"Score: {results[i][1]}\n"
                        embed.description += text
                    embed.description += "```"
                    await sent.edit(embed=embed)
                    return True
            except exceptions:
                await self.restart_db_server()

    async def update(self):
        params = {'token': api_token}
        await self.session.post(url=f"http://{self.db_url}:6969/update", json=params)


def setup(bot: UtilsBot):
    cog = DBApiClient(bot)
    bot.add_cog(cog)
