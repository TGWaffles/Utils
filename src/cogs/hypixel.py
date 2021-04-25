import concurrent.futures
import secrets
import traceback
from functools import partial

import discord
import mcuuid.api
import mcuuid.tools
from aiohttp import web
from discord.ext import commands, tasks

from main import UtilsBot
from src.checks.message_check import check_reply
from src.checks.role_check import is_staff
from src.helpers.hypixel_helper import *
from src.helpers.storage_helper import DataHelper


class Hypixel(commands.Cog):
    def __init__(self, bot: UtilsBot):
        self.bot: UtilsBot = bot
        self.data = DataHelper()
        self.last_reset = datetime.datetime.now()
        # noinspection PyUnresolvedReferences
        self.hypixel_api = HypixelAPI(self.bot, key="4822a8d3-2138-4e4e-a558-3c4f7cc08510")
        self.update_hypixel_info.add_exception_type(discord.errors.DiscordServerError)
        self.update_hypixel_info.add_exception_type(discord.errors.HTTPException)
        self.update_hypixel_info.start()
        self.user_to_files = {}
        self.token_last_used = {}
        self.latest_tokens = []
        self.external_ip = None
        app = web.Application()
        app.add_routes([web.get('/{user}-{uid}.png', self.request_image), web.get('/{user}.png', self.request_image)])
        self.bot.loop.create_task(self.setup_website(app))
        self.bot.loop.create_task(self.hypixel_api.queue_loop())

    async def setup_website(self, app):
        runner = web.AppRunner(app)
        await runner.setup()
        site = web.TCPSite(runner, "0.0.0.0", 2052)
        self.bot.loop.create_task(site.start())
        return

    @staticmethod
    def offline_player(player, experience, user_uuid, threat_index, fkdr):
        return {"name": player.get("displayname"),
                "last_logout": datetime.datetime.fromtimestamp(player.get("lastLogout").timestamp(),
                                                               datetime.timezone.utc),
                "online": False,
                "bedwars_level": get_level_from_xp(experience),
                "bedwars_winstreak": player.get("stats")["Bedwars"]["winstreak"], "uuid": user_uuid,
                "threat_index": threat_index, "fkdr": fkdr}

    async def online_player(self, player, experience, user_uuid, threat_index, fkdr):
        status = await self.hypixel_api.get_status(user_uuid)
        if not status.get("online"):
            return self.offline_player(player, experience, user_uuid, threat_index, fkdr)
        return {"name": player.get("displayname"),
                "last_logout": datetime.datetime.fromtimestamp(player.get("lastLogout").timestamp(),
                                                               datetime.timezone.utc),
                "online": True,
                "bedwars_level": get_level_from_xp(experience),
                "bedwars_winstreak": player.get("stats")["Bedwars"]["winstreak"],
                "game": status.get("gameType"),
                "mode": status.get("mode"), "map": status.get("map"), "uuid": user_uuid, "threat_index": threat_index,
                "fkdr": fkdr}

    async def get_user_stats(self, user_uuid):
        while True:
            try:
                player = await self.hypixel_api.get_player(user_uuid)
                member_online = bool(player.get("lastLogout") < player.get("lastLogin"))
                break
            except TypeError as e:
                print(player.get("lastLogout"))
                print(player.get("lastLogin"))
                print(e)
        experience = player.get("stats")["Bedwars"]["Experience"]
        try:
            fkdr = player.get("stats")['Bedwars']['final_kills_bedwars'] / player.get("stats")['Bedwars'][
                'final_deaths_bedwars']
        except KeyError:
            fkdr = 0
        bedwars_level = get_level_from_xp(experience)
        threat_index = (bedwars_level * (fkdr ** 2)) / 10
        if member_online:
            return await self.online_player(player, experience, user_uuid, threat_index, fkdr)
        else:
            return self.offline_player(player, experience, user_uuid, threat_index, fkdr)

    async def get_expanded_player(self, user_uuid, pool, reset=False):
        player = await self.get_user_stats(user_uuid)
        member_file = await self.bot.loop.run_in_executor(pool, partial(get_file_for_member, player))
        last_file = None
        if not reset:
            if player["name"].lower() in self.user_to_files:
                last_file = BytesIO(self.user_to_files[player["name"].lower()][0])
            if last_file is None:
                same_file = False
            else:
                same_file = await self.bot.loop.run_in_executor(pool, partial(are_equal, last_file, member_file))
                if same_file:
                    member_file.close()
                    member_file = last_file
                else:
                    last_file.close()
        else:
            same_file = False
        player["file"] = member_file.read()
        player["unchanged"] = same_file
        member_file.close()
        return player

    @staticmethod
    async def get_user_embed(member):
        member_embed = discord.Embed(title=member["name"], color=((discord.Colour.red(),
                                                                   discord.Colour.green())[int(member["online"])]),
                                     timestamp=datetime.datetime.utcnow())
        if member["online"]:
            pass
            # if member["mode"] is None:
            #     game_text = "{}: LOBBY".format(member["game"])
            # else:
            #     try:
            #         game_text = "{}: {} ({})".format(member["game"], member["mode"], member["map"]["map"])
            #     except KeyError:
            #         game_text = "{}: {}".format(member["game"], member["mode"])
            # member_embed.add_field(name="Current Game", value=game_text)
        else:
            # member_embed.add_field(name="Last Online", value=member["last_logout"].strftime("%Y/%m/%d %H:%M"))
            member_embed.timestamp = member["last_logout"]

        # member_embed.add_field(name="Hypixel Level", value=member["level"])
        # member_embed.add_field(name="| Bedwars Level", value="| {}".format(member["bedwars_level"]))
        # member_embed.add_field(name="| Bedwars Winstreak", value="| {}".format(member["bedwars_winstreak"]))
        return member_embed

    async def request_image(self, request: web.Request):
        username = request.match_info['user']
        now = datetime.datetime.now()
        data, last_timestamp = self.user_to_files.get(username.lower(), (None, datetime.datetime(1970, 1, 1)))
        if data is None or (now - last_timestamp).total_seconds() > 300:
            uuid = await self.uuid_from_identifier(username)
            if uuid is None:
                return web.Response(status=404)
            valid = await self.check_valid_player(uuid)
            if not valid:
                return web.Response(status=404)
            with concurrent.futures.ProcessPoolExecutor() as pool:
                player = await self.get_expanded_player(uuid, pool, True)
            data = player["file"]
            self.user_to_files[username.lower()] = (data, datetime.datetime.now())
        response = web.StreamResponse()
        response.content_type = "image/png"
        response.content_length = len(data)
        await response.prepare(request)
        await response.write(data)
        return response

    @commands.command(aliases=["hinfo"])
    async def info(self, ctx, username: str):
        now = datetime.datetime.now()
        async with ctx.typing():
            data, last_timestamp = self.user_to_files.get(username.lower(), (None, datetime.datetime(1970, 1, 1)))
            if data is None or (now - last_timestamp).total_seconds() > 300:
                uuid = await self.uuid_from_identifier(username)
                if uuid is None:
                    await ctx.reply(embed=self.bot.create_error_embed("That Minecraft user doesn't exist."))
                    return
                valid = await self.check_valid_player(uuid)
                if not valid:
                    await ctx.reply(embed=self.bot.create_error_embed("That user hasn't played enough bedwars."))
                    return
                with concurrent.futures.ProcessPoolExecutor() as pool:
                    player = await self.get_expanded_player(uuid, pool, True)
                data = player["file"]
                self.user_to_files[username.lower()] = (data, datetime.datetime.now())
            file = BytesIO(data)
            discord_file = discord.File(fp=file, filename=f"{username}.png`")
            await ctx.reply(file=discord_file)

    @commands.command(pass_context=True)
    @is_staff()
    async def hypixel_channel(self, ctx, channel: discord.TextChannel):
        sent = await ctx.send(embed=self.bot.create_processing_embed("Confirm", "Are you sure you want to make {} "
                                                                                "the text channel for hypixel "
                                                                                "updates? \n "
                                                                                "(THIS DELETES ALL CONTENTS) \n"
                                                                                "Type \"yes\" if you're sure.".format(
            channel.mention)))
        try:
            await self.bot.wait_for("message", check=check_reply(ctx.message.author), timeout=15.0)
            await sent.delete()
            processing = await ctx.send(embed=self.bot.create_processing_embed(
                "Converting {}".format(channel.name), "Deleting all prior messages."))
            async for message in channel.history(limit=None):
                await message.delete()
            await processing.edit(embed=self.bot.create_processing_embed(
                "Converting {}".format(channel.name), "Completed all prior messages. Adding channel to database."))
            all_channels = self.data.get("hypixel_channels", {})
            all_channels[str(channel.id)] = []
            self.data["hypixel_channels"] = all_channels
            await processing.edit(embed=self.bot.create_completed_embed("Added Channel!",
                                                                        "Channel added for hypixel info."))
        except asyncio.TimeoutError:
            return

    @staticmethod
    async def uuid_from_identifier(identifier):

        failed = False
        uuid = ""
        try:
            if mcuuid.tools.is_valid_mojang_uuid(identifier):
                uuid = identifier
            elif mcuuid.tools.is_valid_minecraft_username(identifier):
                async with aiohttp.ClientSession() as session:
                    request = await session.get("https://playerdb.co/api/player/minecraft/" + identifier)
                    if request.status != 200:
                        return None
                    json_response = await request.json()
                    if not json_response.get("success", False):
                        return None
                    uuid = json_response.get("data", {}).get("player", {}).get("id", None)
            else:
                failed = True
        except AttributeError:
            failed = True
        if failed:
            return None
        return uuid

    async def username_from_uuid(self, uuid):
        if not mcuuid.tools.is_valid_mojang_uuid(uuid):
            return "Unknown Player"
        async with aiohttp.ClientSession() as session:
            request = await session.get("https://playerdb.co/api/player/minecraft/" + uuid)
            if request.status != 200:
                return None
            json_response = await request.json()
            if not json_response.get("success", False):
                return None
            username = json_response.get("data", {}).get("player", {}).get("username", "Unknown Player")
        return username

    async def check_valid_player(self, uuid):
        try:
            # noinspection PyUnboundLocalVariable
            await self.get_user_stats(uuid)
        except (TypeError, KeyError):
            return False
        return True

    @commands.command(pass_context=True, name="add", description="Adds a player to your server's hypixel channel!",
                      aliases=["hadd", "hypixel_add", "hypixeladd"])
    @is_staff()
    async def add(self, ctx, username: str):
        async with ctx.typing():
            uuid = await self.uuid_from_identifier(username)
            if uuid is None:
                await ctx.reply(embed=self.bot.create_error_embed("Invalid username or uuid {}!".format(username)),
                                delete_after=10)
                await ctx.message.delete()
                return
            valid = await self.check_valid_player(uuid)
            if not valid:
                await ctx.reply(embed=self.bot.create_error_embed("That user is not a valid hypixel bedwars player. "
                                                                  "Get them to play some games first!"))
                return
            all_channels = self.data.get("hypixel_channels", {})
            for channel_id in list(all_channels.keys()).copy():
                channel = self.bot.get_channel(int(channel_id))
                if channel is None:
                    all_channels.pop(str(channel_id))
                    self.data["hypixel_channels"] = all_channels
                    continue
                if channel.guild == ctx.guild:
                    if uuid in all_channels[str(channel_id)]:
                        await ctx.reply(embed=self.bot.create_error_embed("Player already in channel!"))
                        return
                    all_channels[str(channel_id)].append(uuid)
                    self.data["hypixel_channels"] = all_channels
                    await ctx.reply(embed=self.bot.create_completed_embed("User Added!",
                                                                          "User {} has been added to {}.".format(
                                                                              await self.username_from_uuid(uuid),
                                                                              channel.mention)))

    @commands.command(pass_context=True, name="remove", description="Removes a player from your server's "
                                                                    "hypixel channel!",
                      aliases=["hremove", "hypixel_remove", "hypixelremove"])
    @is_staff()
    async def remove(self, ctx, username: str):
        async with ctx.typing():
            uuid = await self.uuid_from_identifier(username)
            if uuid is None:
                await ctx.reply(embed=self.bot.create_error_embed("Invalid username or uuid {}!".format(username)),
                                delete_after=10)
                await ctx.message.delete()
                return
            all_channels = self.data.get("hypixel_channels", {})
            found = False
            for channel in ctx.guild.channels:
                if uuid in all_channels.get(str(channel.id), []):
                    all_channels[str(channel.id)].remove(uuid)
                    self.data["hypixel_channels"] = all_channels
                    await ctx.reply(embed=self.bot.create_completed_embed("User Removed!",
                                                                          "User {} has been removed from {}.".format(
                                                                              await self.username_from_uuid(uuid),
                                                                              channel.mention)))
                    found = True
            if not found:
                await ctx.reply(embed=self.bot.create_error_embed("That user was not found in your hypixel channel!"))

    async def send_embeds(self, channel_id, channel_members, all_members):
        our_members = []
        i = 0
        for member in all_members:
            if member["uuid"] in channel_members:
                our_members.append(member)
        try:
            channel = await self.bot.fetch_channel(channel_id)
        except discord.errors.NotFound:
            channel = None
        if channel is None:
            all_channels = self.data.get("hypixel_channels", {})
            all_channels.pop(str(channel_id))
            self.data["hypixel_channels"] = all_channels
            return
        history = await channel.history(limit=None, oldest_first=True).flatten()
        editable_messages = [message for message in history if message.author == self.bot.user]
        member_files = [member["file"] for member in our_members]
        if (len(editable_messages) != len(our_members) or
                len([message for message in editable_messages if len(message.embeds) == 1]) != len(our_members)):
            await channel.purge(limit=None)
            new_messages = True
        else:
            new_messages = False
        for member, file in zip(our_members, member_files):
            self.user_to_files[member["name"].lower()] = (file, datetime.datetime.now())
            token = secrets.token_urlsafe(16).replace("-", "")
            embed = await self.get_user_embed(member)
            embed.set_image(url="http://{}:2052/{}-{}.png".format(self.external_ip, member["name"], token))
            if new_messages:
                await channel.send(embed=embed)
            else:
                embed_member_name = editable_messages[i].embeds[0].title
                if embed_member_name != member["name"] or not member["unchanged"]:
                    await editable_messages[i].edit(embed=embed)
                i += 1

    @tasks.loop(seconds=45, count=None)
    async def update_hypixel_info(self):
        try:
            if self.external_ip is None:
                async with aiohttp.ClientSession() as session:
                    request = await session.get("https://checkip.amazonaws.com/")
                    text = await request.text()
                    self.external_ip = text.strip()
            all_channels = self.data.get("hypixel_channels", {}).copy()
            member_uuids = set()
            for _, members in all_channels.items():
                for member_uuid in members:
                    member_uuids.add(member_uuid)
            now = datetime.datetime.now()
            reset = (now - self.last_reset).total_seconds() > 180
            member_futures = []
            if reset:
                self.last_reset = datetime.datetime.now()
            with concurrent.futures.ProcessPoolExecutor() as pool:
                for member_uuid in member_uuids:
                    member_futures.append(self.bot.loop.create_task(self.get_expanded_player(member_uuid, pool,
                                                                                             reset)))
                member_dicts = await asyncio.gather(*member_futures)
            offline_members = [member for member in member_dicts if not member["online"]]
            online_members = [member for member in member_dicts if member["online"]]
            offline_members.sort(key=lambda x: float(x["threat_index"]))
            online_members.sort(key=lambda x: float(x["threat_index"]))
            member_dicts = offline_members + online_members
            pending_tasks = []
            for channel in all_channels.keys():
                pending_tasks.append(self.bot.loop.create_task(
                    self.send_embeds(channel, set(all_channels[channel]), member_dicts)))
            await asyncio.gather(*pending_tasks)
        except Exception as e:
            print("hypixel error")
            print(traceback.format_exc())

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author == self.bot.user:
            return
        all_channels = self.data.get("hypixel_channels", {}).keys()
        if str(message.channel.id) in all_channels:
            await message.delete()


def setup(bot):
    cog = Hypixel(bot)
    bot.add_cog(cog)
