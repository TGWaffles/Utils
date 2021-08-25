import json
import secrets
import base64
import aspell
import discord

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
        app.add_routes([web.post('/speak', self.handle_speak_message), web.post('/disconnect', self.handle_disconnect),
                        web.get('/check_access', self.check_access), web.get('/avatar_urls', self.avatar_urls),
                        web.get('/regen_img/{data}', self.regen_image)])
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

    async def handle_disconnect(self, request: web.Request):
        try:
            request_json = await request.json()
            user_doc = await self.api_db.find_one({"key": request_json.get("token", "none")})
            assert user_doc is not None
        except (TypeError, json.JSONDecodeError):
            return web.Response(status=400)
        except AssertionError:
            return web.Response(status=401)
        tts_cog = self.bot.get_cog("TTS")
        self.bot.loop.create_task(tts_cog.disconnect_from_api(user_doc.get("_id")))
        return web.Response(status=202)

    async def handle_speak_message(self, request: web.Request):
        try:
            request_json = await request.json()
            print(request_json)
            user_doc = await self.api_db.find_one({"key": request_json.get("token", "none")})
            assert user_doc is not None
        except (TypeError, json.JSONDecodeError):
            return web.Response(status=400)
        except AssertionError:
            return web.Response(status=401)
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
                print("it's not none")
                member_id = int(request_json.get("member_id"))
                print(member_id)
        tts_cog = self.bot.get_cog("TTS")
        if autocorrect:
            content = ' '.join([self.find_autocorrect(word) for word in content.split(" ")])
        self.bot.loop.create_task(tts_cog.speak_id_content(int(member_id), content))
        return web.Response(status=202)

    async def check_access(self, request: web.Request):
        try:
            request_json = await request.json()
            user_id = request_json.get("user_id")
            channel_id = request_json.get("channel_id")
            assert user_id is not None and channel_id is not None
        except (TypeError, json.JSONDecodeError):
            return web.Response(status=400)
        except AssertionError:
            return web.Response(status=400)
        channel: discord.TextChannel = self.bot.get_channel(channel_id)
        if channel is None:
            try:
                channel = await self.bot.fetch_channel(channel_id)
            except discord.errors.NotFound:
                return web.Response(status=404)
        guild: discord.Guild = channel.guild
        member = guild.get_member(user_id)
        if member is None:
            try:
                member = await guild.fetch_member(user_id)
            except discord.errors.NotFound:
                return web.Response(status=401)
        permissions: discord.Permissions = channel.permissions_for(member)
        return web.json_response({"has_access": permissions.read_messages, "can_delete": permissions.manage_messages})

    async def avatar_urls(self, request: web.Request):
        try:
            request_json = await request.json()
            user_ids = request_json.get("user_ids", [])
            assert len(user_ids) > 0
        except (TypeError, json.JSONDecodeError):
            return web.Response(status=400)
        except AssertionError:
            return web.Response(status=400)
        resolved_dict = {}
        for user_id in user_ids:
            user: discord.User = self.bot.get_user(user_id)
            if user is None:
                try:
                    user = await self.bot.fetch_user(user_id)
                except discord.errors.NotFound:
                    resolved_dict[user_id] = "https://discordapp.com/assets/dd4dbc0016779df1378e7812eabaa04d.png"
                    continue
            resolved_dict[user_id] = str(user.avatar_url)
        return web.json_response({"resolved": resolved_dict})

    @commands.command()
    async def api_key(self, ctx):
        await ctx.reply(embed=self.bot.create_completed_embed("Generated API Key",
                                                              "I have DM'd you your api key."))
        key = secrets.token_urlsafe(16)
        user_document = {"_id": ctx.author.id, "key": key}
        await self.bot.mongo.force_insert(self.api_db, user_document)
        await ctx.author.send("Your API key is: {}".format(key))

    async def regen_image(self, request: web.Request):
        print("regen request received")
        b64_data = request.match_info['data']
        print(b64_data)
        data = base64.urlsafe_b64decode(b64_data)
        response = web.StreamResponse()
        response.content_type = "image/jpg"
        response.content_length = len(data)
        response.headers["Cache-Control"] = "max-age=15"
        await response.prepare(request)
        await response.write(data)
        return response


def setup(bot):
    cog = API(bot)
    bot.add_cog(cog)
