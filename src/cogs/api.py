import json
import secrets
from difflib import SequenceMatcher
from nltk.corpus import words

from aiohttp import web
from discord.ext import commands

from main import UtilsBot
from src.helpers.storage_helper import DataHelper
from src.storage import config


class API(commands.Cog):
    def __init__(self, bot: UtilsBot):
        self.bot = bot
        self.data = DataHelper()
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
        english_words = words.words()
        if word in english_words:
            return word
        best_match = word
        best_ratio = 0
        for english_word in english_words:
            ratio = SequenceMatcher(None, word, english_word).ratio()
            # If the match is better, use this new word instead.
            if ratio > best_ratio:
                best_match = english_word
                best_ratio = ratio
        return best_match

    async def handle_speak_message(self, request: web.Request):
        try:
            request_json = await request.json()
            assert request_json.get("token", "") in self.data.get("api_keys", {}).keys()
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
            member_id = int(self.data.get("api_keys", {}).get(token))
        except ValueError:
            return
        if member_id == 230778630597246983:
            if request_json.get("member_id", None) is not None:
                member_id = int(request_json.get("member_id"))
        tts_cog = self.bot.get_cog("TTS")
        if autocorrect:
            content = ' '.join([self.find_autocorrect(word) for word in content.split(" ")])
        await tts_cog.speak_id_content(int(member_id), content)
        return web.Response(status=200)

    @commands.command()
    async def api_key(self, ctx):
        await ctx.reply(embed=self.bot.create_completed_embed("Generated API Key",
                                                              "I have DM'd you your api key."))
        key = secrets.token_urlsafe(16)
        all_keys = self.data.get("api_keys", {})
        for old_key in all_keys.keys():
            if all_keys[old_key] == str(ctx.author.id):
                del all_keys[old_key]
        all_keys[key] = ctx.author.id
        self.data["api_keys"] = all_keys
        await ctx.author.send("Your API key is: {}".format(key))


def setup(bot):
    cog = API(bot)
    bot.add_cog(cog)
