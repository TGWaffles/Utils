import asyncio
import json
import secrets

from discord.ext import commands

from main import UtilsBot
from src.helpers.storage_helper import DataHelper


def get_protocol(bot):
    class ReceiveAPIMessage(asyncio.Protocol):
        def data_received(self, data: bytes) -> None:
            json_content = json.loads(data.decode())
            storage = DataHelper()
            if json_content.get("key", "") not in storage.get("api_keys", {}).keys():
                return
            if json_content.get("type", "") == "tts_message":
                content = json_content.get("message_content", "")
                try:
                    member_id = int(storage.get("api_keys", {}).get(json_content.get("key", "")))
                except ValueError:
                    return
                bot.bot.loop.create_task(bot.speak_id_content(int(member_id), content))
    return ReceiveAPIMessage


async def start_server(bot):
    loop = bot.bot.loop
    server = await loop.create_server(get_protocol(bot), '0.0.0.0', 43023)
    async with server:
        await server.serve_forever()


class API(commands.Cog):
    def __init__(self, bot: UtilsBot):
        self.bot = bot

    @commands.command()
    def api_key(self, ctx):
        await ctx.reply(embed=self.bot.create_completed_embed("Generated API Key",
                                                              "I have DM'd you your api key."))
        key = secrets.token_urlsafe(16)
        storage = DataHelper()
        all_keys = storage.get("api_keys", {})
        all_keys[ctx.author.id] = key
        storage["api_keys"] = all_keys
        await ctx.author.send("Your API key is: {}".format(key))


def setup(bot):
    cog = API(bot)
    bot.add_cog(cog)
