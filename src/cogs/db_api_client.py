import asyncio
import datetime

import aiohttp
import aiohttp.client_exceptions
import discord
from discord.ext import commands

from main import UtilsBot
from src.storage.token import api_token


class DBApiClient(commands.Cog):
    def __init__(self, bot: UtilsBot):
        self.bot = bot
        self.bot.database_handler = self
        self.session = aiohttp.ClientSession()
        self.db_url = "tgwaffles.me"
        self.bot.loop.create_task(self.ping_db_server())
        self.last_ping = datetime.datetime.now()

    async def ping_db_server(self):
        while True:
            try:
                params = {'timestamp': datetime.datetime.utcnow().timestamp()}
                async with self.session.get(url=f"http://{self.db_url}:6970/ping", timeout=10, json=params) as request:
                    json_info = await request.json()
                    self.last_ping = datetime.datetime.now()
                    if json_info.get("time_delay", 100) > 3:
                        await self.restart_db_server()
                        await asyncio.sleep(10)
            except aiohttp.client_exceptions.ClientConnectorError:
                await self.restart_db_server()
                await asyncio.sleep(10)
            except asyncio.exceptions.TimeoutError:
                await self.restart_db_server()
                await asyncio.sleep(10)
            await asyncio.sleep(1)

    async def restart_db_server(self):
        params = {'token': api_token}
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

    async def get_someone_id(self, guild_id):
        params = {'token': api_token, "guild_id": guild_id}
        while True:
            try:
                async with self.session.get(url=f"http://{self.db_url}:6970/someone", timeout=10, json=params) as request:
                    response_json = await request.json()
                    return response_json.get("member_id")
            except asyncio.exceptions.TimeoutError:
                await self.restart_db_server()

    @commands.command()
    async def snipe(self, ctx):
        sent = await ctx.reply(embed=self.bot.create_processing_embed("Processing...", "Getting sniped message..."))
        params = {'token': api_token, 'channel_id': ctx.channel.id}
        while True:
            try:
                async with self.session.get(url=f"http://{self.db_url}:6970/snipe", timeout=10, json=params) as request:
                    if request.status != 200:
                        await sent.edit(embed=self.bot.create_error_embed("Couldn't snipe!"))
                        return
                    response_json = await request.json()
                    user_id = response_json.get("user_id")
                    content = response_json.get("content")
                    timestamp = datetime.datetime.fromisoformat(response_json.get("timestamp"))
                    user = self.bot.get_user(user_id)
                    embed = discord.Embed(title="Sniped Message", colour=discord.Colour.red())
                    embed.set_author(name=user.name, icon_url=user.avatar_url)
                    embed.description = content
                    embed.timestamp = timestamp
                    await sent.edit(embed=embed)
                    return True
            except asyncio.exceptions.TimeoutError:
                await self.restart_db_server()

    @commands.command(description="Count how many times a phrase has been said!")
    async def count(self, ctx, *, phrase):
        if len(phrase) > 223:
            await ctx.reply(embed=self.bot.create_error_embed("That phrase was too long!"))
            return
        sent = await ctx.reply(embed=self.bot.create_processing_embed("Counting...",
                                                                      f"Counting how many times \"{phrase}\""
                                                                      f"has been said..."))
        params = {"phrase": phrase, "guild_id": ctx.guild.id}
        while True:
            try:
                async with self.session.get(url=f"http://{self.db_url}:6970/global_phrase_count", timeout=10,
                                            json=params) as request:
                    if request.status != 200:
                        await sent.edit(embed=self.bot.create_error_embed("Couldn't count!"))
                        return
                    response_json = await request.json()
                    amount = response_json.get("amount")
                    embed = self.bot.create_completed_embed(
                        f"Number of times \"{phrase}\" has been said:", f"**{amount}** times!")
                    embed.set_footer(text="If you entered a phrase, remember to surround it in **straight** quotes ("
                                          "\"\")!")
                    await sent.edit(embed=embed)
                    return True
            except asyncio.exceptions.TimeoutError:
                await self.restart_db_server()

    async def update(self):
        params = {'token': api_token}
        await self.session.post(url=f"http://{self.db_url}:6969/update", json=params)


def setup(bot: UtilsBot):
    cog = DBApiClient(bot)
    bot.add_cog(cog)
