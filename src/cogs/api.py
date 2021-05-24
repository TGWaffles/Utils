import json
import secrets
import aspell

from aiohttp import web
from discord.ext import commands

from main import UtilsBot
from src.storage import config


class API(commands.Cog):
    def __init__(self, bot: UtilsBot):
        self.bot = bot
        self.speller = aspell.Speller('lang', 'en')
        self.api_db = self.bot.mongo.client.api.users
        app = web.Application()
        app.add_routes([web.post('/speak', self.handle_speak_message)])
        # noinspection PyProtectedMember
        self.bot.loop.create_task(self.start_site(app))

    async def start_site(self, app):
        runner = web.AppRunner(app)
        await runner.setup()
        site = web.TCPSite(runner, "0.0.0.0", config.api_port)
        self.bot.loop.create_task(site.start())
        return

    def find_autocorrect(self, word):
        suggestions = self.speller.suggest(word)
        return suggestions[0] if len(suggestions) > 0 else word

    async def handle_speak_message(self, request: web.Request):
        try:
            request_json = await request.json()
            user_doc = await self.api_db.find_one({"key": request_json.get("token", "none")})
            assert user_doc is not None
        except (TypeError, json.JSONDecodeError):
            return web.Response(status=400)
        except AssertionError:
            return web.Response(status=401)
        token = request_json.get("token", "")
        content = request_json.get("content", "")
        autocorrect = request_json.get("autocorrect", False)
        if content == "":
            return web.Response(status=400)
        try:
            member_id = user_doc.get("_id")
        except ValueError:
            return
        if member_id == 230778630597246983:
            if request_json.get("member_id", None) is not None:
                member_id = int(request_json.get("member_id"))
        tts_cog = self.bot.get_cog("TTS")
        if autocorrect:
            content = ' '.join([self.find_autocorrect(word) for word in content.split(" ")])
        self.bot.loop.create_task(tts_cog.speak_id_content(int(member_id), content))
        return web.Response(status=202)

    @commands.command()
    async def api_key(self, ctx):
        await ctx.reply(embed=self.bot.create_completed_embed("Generated API Key",
                                                              "I have DM'd you your api key."))
        key = secrets.token_urlsafe(16)
        user_document = {"_id": ctx.author.id, "key": key}
        await self.bot.mongo.force_insert(self.api_db, user_document)
        await ctx.author.send("Your API key is: {}".format(key))


def setup(bot):
    cog = API(bot)
    bot.add_cog(cog)
