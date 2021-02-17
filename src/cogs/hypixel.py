import asyncio
import datetime

import PIL.Image
import PIL.ImageDraw
import PIL.ImageFont
import asyncpixel
import asyncpixel.exceptions.exceptions
import discord
import mcuuid.api
import mcuuid.tools
import concurrent.futures
import secrets
from functools import partial
from discord.ext import commands, tasks
from io import BytesIO
from aiohttp import web

from main import UtilsBot
from src.checks.message_check import check_reply
from src.checks.role_check import is_staff
from src.helpers.hypixel_helper import *
from src.helpers.storage_helper import DataHelper


def find_font_size(draw, text, min_width, max_width, max_height):
    size = 1
    font = PIL.ImageFont.truetype("arial.ttf", size)
    last_size = draw.textsize(text, font=font)
    while last_size[0] < min_width and last_size[1] < max_height:
        size += 1
        font = PIL.ImageFont.truetype("arial.ttf", size)
        last_size = draw.textsize(text, font=font)
    if last_size[0] > max_width or last_size[1] > max_height:
        size -= 1
        font = PIL.ImageFont.truetype("arial.ttf", size)
    return font


def get_colour_from_threat(threat_index):
    if threat_index <= 45:
        return 170, 170, 170
    elif threat_index <= 80:
        return 85, 255, 85
    elif threat_index <= 120:
        return 0, 170, 0
    elif threat_index <= 225:
        return 255, 255, 85
    elif threat_index <= 325:
        return 255, 170, 0
    elif threat_index <= 650:
        return 255, 85, 85
    else:
        return 170, 0, 0


# def draw_table(members):
#     for member in members:
#         if member["online"]:
#             if member["mode"] is None:
#                 game_text = "{}: \nLOBBY".format(member["game"])
#             else:
#                 try:
#                     game_text = "{}: \n{} \n({})".format(member["game"], member["mode"], member["map"]["map"])
#                 except KeyError:
#                     game_text = "{}: \n{}".format(member["game"], member["mode"])
#         else:
#             game_text = member["last_logout"].strftime("%Y/%m/%d %H:%M")
#         member["game"] = game_text
#     final_file = BytesIO()
#     size = 2048
#     width = size
#     column_height = size // 16
#     offset_from_top = size // 48
#     height = column_height * (len(members) + 1)
#     image = PIL.Image.new('RGB', (width, height), color=(128, 128, 128))
#     drawer = PIL.ImageDraw.Draw(image)
#     columns = ["Name", "Last Online", "Level", "Winstreak", "Threat Index", "FKDR"]
#     column_to_date = lambda member: [member["name"], member["game"],
#                                      member["bedwars_level"], member["bedwars_winstreak"],
#                                      round(member["threat_index"], 1), round(member["fkdr"], 1)]
#     online_count = len([1 for member in members if member["online"]])
#     if online_count > 0:
#         member_index = len(members) - online_count
#         text_y = member_index * column_height + offset_from_top
#         highest_y = (text_y + ((member_index + 1) * column_height + offset_from_top)) // 2
#         # highest_y = height - (online_count * column_height)
#         drawer.rectangle(xy=[(0, highest_y), (width, height)], width=0, fill=(32, 128, 32))
#         line_y = (offset_from_top + column_height + offset_from_top) // 2
#         drawer.rectangle(xy=[(0, line_y), (width, highest_y)], width=0, fill=(128, 32, 32))
#     else:
#         line_y = (offset_from_top + column_height + offset_from_top) // 2
#         drawer.rectangle(xy=[(0, line_y), (width, height)], width=0, fill=(128, 32, 32))
#     line_distance = size // len(columns)
#     for column in range(len(columns) - 1):
#         x = (column + 1) * line_distance
#         drawer.line([(x, 0), (x, height)], width=(size // (len(columns) * 32)), fill=(0, 0, 0))
#     for column in range(len(columns)):
#         text_x = (column * line_distance + (column + 1) * line_distance) // 2
#         text_y = offset_from_top
#         font = find_font_size(drawer, columns[column], (line_distance * 3) // 4, line_distance, column_height)
#         drawer.text((text_x, text_y), columns[column], fill=(0, 0, 0), font=font, anchor="mm")
#         line_y = (text_y + column_height + offset_from_top) // 2
#         drawer.line([(0, line_y), (width, line_y)], width=(size // (len(columns) * 32)),
#                     fill=(0, 0, 0))
#     for member_index in range(len(members)):
#         text_y = (member_index + 1) * column_height + offset_from_top
#         member_data = column_to_date(members[member_index])
#         fill = get_colour_from_threat(members[member_index]["threat_index"])
#         for column in range(len(columns)):
#             text_x = (column * line_distance + (column + 1) * line_distance) // 2
#             text = str(member_data[column])
#             font = find_font_size(drawer, text, (line_distance * 3) // 4, line_distance, column_height)
#             drawer.text((text_x, text_y), text, fill=fill, font=font, anchor="mm")
#         if member_index < len(members) - 1:
#             line_y = (text_y + ((member_index + 2) * column_height + offset_from_top)) // 2
#             drawer.line([(0, line_y), (width, line_y)], width=(size // (len(columns) * 32)),
#                         fill=(0, 0, 0))
#     image.save(fp=final_file, format="png")
#     final_file.seek(0)
#     return final_file


def get_file_for_member(member):
    final_file = BytesIO()
    size = 1024
    width = size
    height = width // 4
    if member["online"]:
        fill = (16, 64, 16)
    else:
        fill = (64, 16, 16)
    image = PIL.Image.new('RGB', (width, height), color=fill)
    draw = PIL.ImageDraw.Draw(image)
    name_colour = get_colour_from_threat(member["threat_index"])
    name_font = PIL.ImageFont.truetype("arial.ttf", size // 16)
    # Write Name
    name_x = width // 2
    name_y = height // 8
    draw.text((name_x, name_y), member["name"], font=name_font, anchor="mm", fill=name_colour)

    # Write last online or current game.
    if member["online"]:
        if member["mode"] is None:
            game_text = "{}: \nLOBBY".format(member["game"])
        else:
            try:
                game_text = "{}: \n{} ({})".format(member["game"], member["mode"], member["map"]["map"])
            except KeyError:
                game_text = "{}: \n{}".format(member["game"], member["mode"])
        last_played_heading = "Current Game"
    else:
        last_played_heading = "Last Online"
        game_text = "{}".format(member["last_logout"].strftime("%Y/%m/%d %H:%M"))
    top_line_height = height // 8
    last_played_y = height - top_line_height
    last_played_font = PIL.ImageFont.truetype("arial.ttf", size // 32)
    regular_text_fill = (255, 100, 255)
    last_played_x = width // 64
    # last_played_x = max([draw.textsize(line, font=last_played_font)[0]
    #                      for line in game_text.split("\n")]) // 2 + width // 64
    for line in game_text.split("\n")[::-1]:
        draw.text((last_played_x, last_played_y), line, font=last_played_font, anchor="lm", fill=regular_text_fill,
                  align="center")
        last_played_y -= draw.textsize(line, font=last_played_font)[1]
    draw.text((width // 64, last_played_y), last_played_heading, font=last_played_font, anchor="lm",
              fill=regular_text_fill)
    win_streak = "Winstreak\n{}".format(member["bedwars_winstreak"])
    win_streak_height = top_line_height
    # win_streak_level_x = width - (max([draw.textsize(line, font=last_played_font)[0]
    #                                    for line in win_streak.split("\n")]) // 2 + width // 64)
    win_streak_level_x = width - width // 64
    for line in win_streak.split("\n"):
        draw.text((win_streak_level_x, win_streak_height), line,
                  font=last_played_font, anchor="rm", fill=regular_text_fill)
        win_streak_height += draw.textsize(line, font=last_played_font)[1]
    level_height = height - top_line_height
    level_text = "Level\n{}".format(member["bedwars_level"])
    for line in level_text.split("\n")[::-1]:
        draw.text((win_streak_level_x, level_height), line,
                  font=last_played_font, anchor="rm", fill=regular_text_fill)
        level_height -= draw.textsize(line, font=last_played_font)[1]

    # fkdr_x = max([-(win_streak_level_x-width), last_played_x])
    fkdr_x = width // 64
    fkdr_text = "FKDR\n{}".format(round(member["fkdr"], 2))
    fkdr_height = top_line_height
    for line in fkdr_text.split("\n"):
        draw.text((fkdr_x, fkdr_height), line, font=last_played_font, anchor="lm",
                  fill=regular_text_fill, aligh="center")
        fkdr_height += draw.textsize(line, font=last_played_font)[1]

    threat_index_x = width // 2
    threat_index_y = height // 2

    threat_index_text = "Threat Index\n{}".format(round(member["threat_index"], 1))
    draw.text((threat_index_x, threat_index_y), threat_index_text, font=last_played_font, anchor="mm",
              fill=regular_text_fill, align="center")

    image.save(fp=final_file, format="png")
    final_file.seek(0)
    return final_file


class Hypixel(commands.Cog):
    def __init__(self, bot: UtilsBot):
        self.bot: UtilsBot = bot
        self.data = DataHelper()
        # noinspection PyUnresolvedReferences
        self.hypixel = asyncpixel.Client("e823fbc4-e526-4fbb-bf15-37e543aebdd6")
        self.update_hypixel_info.add_exception_type(discord.errors.DiscordServerError)
        self.update_hypixel_info.add_exception_type(discord.errors.HTTPException)
        self.update_hypixel_info.add_exception_type(asyncpixel.exceptions.exceptions.ApiNoSuccess)
        self.update_hypixel_info.start()
        self.name_to_files = {}
        app = web.Application()
        app.add_routes([web.get('/{uid}.png', self.request_image)])
        # noinspection PyProtectedMember
        self.bot.loop.create_task(web._run_app(app, port=8800))

    async def get_user_stats(self, user_uuid):
        player = await self.hypixel.get_player(user_uuid)
        member_online = bool(player.lastLogout < player.lastLogin)
        experience = player.stats["Bedwars"]["Experience"]
        fkdr = player.stats['Bedwars']['final_kills_bedwars'] / player.stats['Bedwars']['final_deaths_bedwars']
        bedwars_level = get_level_from_xp(experience)
        threat_index = (bedwars_level * (fkdr ** 2)) / 10
        if member_online:
            status = await self.hypixel.get_player_status(user_uuid)
            return {"name": player.displayname,
                    "level": player.level, "last_logout": datetime.datetime.fromtimestamp(player.lastLogout.timestamp(),
                                                                                          datetime.timezone.utc),
                    "online": member_online,
                    "bedwars_level": get_level_from_xp(experience),
                    "bedwars_winstreak": player.stats["Bedwars"]["winstreak"],
                    "game": status.gameType,
                    "mode": status.mode, "map": status.map, "uuid": user_uuid, "threat_index": threat_index,
                    "fkdr": fkdr}
        else:
            return {"name": player.displayname,
                    "level": player.level, "last_logout": datetime.datetime.fromtimestamp(player.lastLogout.timestamp(),
                                                                                          datetime.timezone.utc),
                    "online": member_online,
                    "bedwars_level": get_level_from_xp(experience),
                    "bedwars_winstreak": player.stats["Bedwars"]["winstreak"], "uuid": user_uuid,
                    "threat_index": threat_index, "fkdr": fkdr}

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
        file = self.name_to_files.get(request.match_info['uid'], None)
        if file is None:
            return web.Response(status=404)
        response = web.StreamResponse()
        response.content_type = "image/png"
        data = file.read()
        file.seek(0)
        response.content_length = len(data)
        await response.prepare(request)
        await response.write(data)
        return response

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

    async def uuid_from_identifier(self, ctx, identifier):
        failed = False
        try:
            if mcuuid.tools.is_valid_mojang_uuid(identifier):
                uuid = identifier
            elif mcuuid.tools.is_valid_minecraft_username(identifier):
                uuid = mcuuid.api.GetPlayerData(identifier).uuid
            else:
                failed = True
        except AttributeError:
            failed = True
        if failed:
            await ctx.reply(embed=self.bot.create_error_embed("Invalid username or uuid {}!".format(identifier)),
                            delete_after=10)
            await ctx.message.delete()
            return
        try:
            # noinspection PyUnboundLocalVariable
            await self.get_user_stats(uuid)
        except (TypeError, KeyError):
            await ctx.reply(embed=self.bot.create_error_embed("That player is not a valid Hypixel Bedwars Player!"))
            return
        return uuid

    @commands.command(pass_context=True, name="add", description="Adds a player to your server's hypixel channel!",
                      aliases=["hadd", "hypixel_add", "hypixeladd"])
    @is_staff()
    async def add(self, ctx, username: str):
        uuid = await self.uuid_from_identifier(ctx, username)
        if uuid is None:
            return
        all_channels = self.data.get("hypixel_channels", {})
        for channel_id in all_channels.keys():
            channel = self.bot.get_channel(int(channel_id))
            if channel.guild == ctx.guild:
                if uuid in all_channels[str(channel_id)]:
                    await ctx.reply(embed=self.bot.create_error_embed("Player already in channel!"))
                    return
                all_channels[str(channel_id)].append(uuid)
                self.data["hypixel_channels"] = all_channels
                await ctx.reply(embed=self.bot.create_completed_embed("User Added!",
                                                                      "User {} has been added to {}.".format(
                                                                          mcuuid.api.GetPlayerData(uuid).username,
                                                                          channel.mention)))

    @commands.command(pass_context=True, name="remove", description="Removes a player to your server's "
                                                                    "hypixel channel!",
                      aliases=["hremove", "hypixel_remove", "hypixelremove"])
    @is_staff()
    async def remove(self, ctx, username: str):
        uuid = await self.uuid_from_identifier(ctx, username)
        if uuid is None:
            return
        all_channels = self.data.get("hypixel_channels", {})
        for channel_id in all_channels.keys():
            channel = self.bot.get_channel(int(channel_id))
            if uuid in self.data.get("hypixel_channels", {})[str(channel_id)]:
                all_channels[str(channel_id)].remove(uuid)
                self.data["hypixel_channels"] = all_channels
                await ctx.reply(embed=self.bot.create_completed_embed("User Removed!",
                                                                      "User {} has been removed from {}.".format(
                                                                          mcuuid.api.GetPlayerData(uuid).username,
                                                                          channel.mention)))

    async def send_embeds(self, channel_id, channel_members, all_members):
        our_members = []
        i = 0
        for member in all_members:
            if member["uuid"] in channel_members:
                our_members.append(member)
        channel = await self.bot.fetch_channel(channel_id)
        history = await channel.history(limit=None, oldest_first=True).flatten()
        editable_messages = [message for message in history if message.author == self.bot.user]
        futures = []
        with concurrent.futures.ProcessPoolExecutor() as pool:
            for member in our_members:
                futures.append(asyncio.get_event_loop().run_in_executor(pool, partial(get_file_for_member, member)))
        member_files = await asyncio.gather(*futures)
        if len(editable_messages) != len(our_members):
            await channel.purge(limit=None)
            new_messages = True
        else:
            new_messages = False
        added_uids = []
        for member, file in zip(our_members, member_files):
            token = secrets.token_urlsafe(16)
            self.name_to_files[token] = file
            added_uids.append(token)
            embed = await self.get_user_embed(member)
            embed.set_image(url="http://tgwaffles.me:8800/{}.png".format(token))
            if new_messages:
                await channel.send(embed=embed)
            else:
                await editable_messages[i].edit(embed=embed)
                i += 1
        removing_tokens = [token for token in self.name_to_files.keys() if token not in added_uids]
        for token in removing_tokens:
            self.name_to_files[token].close()
            del self.name_to_files[token]

    @tasks.loop(seconds=5, count=None)
    async def update_hypixel_info(self):
        all_channels = self.data.get("hypixel_channels", {}).copy()
        member_uuids = set()
        for _, members in all_channels.items():
            for member_uuid in members:
                member_uuids.add(member_uuid)
        member_dicts = []
        for member_uuid in member_uuids:
            while True:
                try:
                    member_dicts.append(await self.get_user_stats(member_uuid))
                    break
                except asyncpixel.exceptions.exceptions.RateLimitError:
                    await asyncio.sleep(0.5)
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
