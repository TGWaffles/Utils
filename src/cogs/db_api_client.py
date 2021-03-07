import asyncio
import datetime

import aiohttp
import aiohttp.client_exceptions
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

    async def ping_db_server(self):
        while True:
            try:
                params = {'timestamp': datetime.datetime.utcnow().timestamp()}
                async with self.session.get(url=f"http://{self.db_url}:6970/ping", timeout=10, json=params) as request:
                    json_info = await request.json()
                    if json_info.get("time_delay", 100) > 3:
                        await self.restart_db_server()
            except aiohttp.client_exceptions.ClientConnectorError:
                await self.restart_db_server()
            await asyncio.sleep(1)

    async def restart_db_server(self):
        params = {'token': api_token}
        try:
            async with self.session.get(url=f"http://{self.db_url}:6970/restart", timeout=10, json=params) as request:
                await request.json()
                print("Restarted DB server")
        except aiohttp.client_exceptions.ClientConnectorError:
            await self.session.post(url=f"http://{self.db_url}:6969/restart", json=params)

    async def get_someone_id(self, guild_id):
        params = {'token': api_token, "guild_id": guild_id}
        async with self.session.get(url=f"http://{self.db_url}:6970/someone", timeout=10, json=params) as request:
            response_json = await request.json()
            return response_json.get("member_id")

    async def update(self):
        params = {'token': api_token}
        await self.session.post(url=f"http://{self.db_url}:6969/update", json=params)


def setup(bot: UtilsBot):
    cog = DBApiClient(bot)
    bot.add_cog(cog)
