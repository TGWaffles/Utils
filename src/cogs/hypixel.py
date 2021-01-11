import discord
import datetime
import asyncio
import asyncpixel
import mcuuid.tools
import mcuuid.api

from src.storage import config, messages
from discord.ext import commands
from main import UtilsBot
from src.checks.role_check import is_staff
from src.checks.user_check import is_owner
from src.checks.guild_check import monkey_check
from src.checks.message_check import check_reply
from src.helpers.storage_helper import DataHelper
from src.helpers.hypixel_helper import *


class Hypixel(commands.Cog):
    def __init__(self, bot: UtilsBot):
        self.bot: UtilsBot = bot
        self.data = DataHelper()
        self.hypixel = asyncpixel.Client("e823fbc4-e526-4fbb-bf15-37e543aebdd6")

    async def get_user_stats(self, user_uuid):
        player = await self.hypixel.get_player(user_uuid)
        member_online = bool(player.lastLogout < player.lastLogin)
        experience = player.stats["Bedwars"]["Experience"]
        if member_online:
            status = await self.hypixel.get_player_status(user_uuid)
            return {"name": player.displayname,
                    "level": player.level, "last_logout": player.lastLogout,
                    "online": member_online,
                    "bedwars_level": get_level_from_xp(experience),
                    "bedwars_winstreak": player.stats["Bedwars"]["winstreak"],
                    "game": status.gameType,
                    "mode": status.mode, "map": status.map}
        else:
            return {"name": player.displayname,
                    "level": player.level, "last_logout": player.lastLogout,
                    "online": member_online,
                    "bedwars_level": get_level_from_xp(experience),
                    "bedwars_winstreak": player.stats["Bedwars"]["winstreak"]}

    async def get_user_embed(self, user_uuid):
        member = await self.get_user_stats(user_uuid)
        member_embed = discord.Embed(title=member["name"], color=((discord.Colour.red(),
                                                                   discord.Colour.green())[int(member["online"])]),
                                     timestamp=datetime.datetime.utcnow())
        if member["online"]:
            if member["mode"] is None:
                game_text = "{}: LOBBY".format(member["game"])
            else:
                try:
                    game_text = "{}: {} ({})".format(member["game"], member["mode"], member["map"]["map"])
                except KeyError:
                    game_text = "{}: {}".format(member["game"], member["mode"])
            member_embed.add_field(name="Current Game", value=game_text)
        else:
            member_embed.add_field(name="Last Online", value=member["last_logout"].strftime("%Y/%m/%d %H:%M"))
            member_embed.timestamp = member["last_logout"]

        # member_embed.add_field(name="Hypixel Level", value=member["level"])
        member_embed.add_field(name="| Bedwars Level", value="| {}".format(member["bedwars_level"]))
        member_embed.add_field(name="| Bedwars Winstreak", value="| {}".format(member["bedwars_winstreak"]))
        return member_embed

    @commands.command(pass_context=True)
    async def hypixel_channel(self, ctx, channel: discord.TextChannel):
        sent = await ctx.send(embed=self.bot.create_processing_embed("Confirm", "Are you sure you want to make {} "
                                                                                "the text channel for hypixel "
                                                                                "updates? \n "
                                                                                "(THIS DELETES ALL CONTENTS) \n"
                                                                                "Type \"yes\" if you're sure.".format(
            channel.mention)))
        try:
            await sent.delete()
            processing = await ctx.message.send(embed=self.bot.create_processing_embed(
                "Converting {}".format(channel.name), "Deleting all prior messages."))
            async for message in channel.history(limit=None):
                await message.delete()
            await processing.edit(embed=self.bot.create_processing_embed(
                "Converting {}".format(channel.name), "Completed all prior messages. Adding channel to database."))
            await self.bot.wait_for("message", check=check_reply(ctx.message.author), timeout=15.0)
            self.data["hypixel_channels"][str(channel.id)] = []
            await processing.edit(embed=self.bot.create_completed_embed("Added Channel!",
                                                                        "Channel added for hypixel info."))
        except asyncio.TimeoutError:
            return

    async def uuid_from_identifier(self, ctx, identifier):
        if mcuuid.tools.is_valid_mojang_uuid(identifier):
            uuid = identifier
        elif mcuuid.tools.is_valid_minecraft_username(identifier):
            uuid = mcuuid.api.GetPlayerData(identifier).uuid
        else:
            await ctx.reply(self.bot.create_error_embed("Invalid username or uuid {}!".format(username)),
                            delete_after=10)
            await ctx.message.delete()
            return
        try:
            await self.get_user_stats(uuid)
        except TypeError:
            await ctx.reply(embed=self.bot.create_error_embed("That player is not a valid Hypixel Bedwars Player!"))
            return
        return uuid


    @commands.command(pass_context=True)
    @is_staff()
    async def add(self, ctx, username: str):
        uuid = await self.uuid_from_identifier(username)
        if uuid is None:
            return
        all_channels = self.data["hypixel_channels"]
        for channel_id in all_channels.keys():
            channel = self.bot.get_channel(int(channel_id))
            if channel.guild == ctx.guild:
                all_channels[channel_id].append(uuid)
                self.data["hypixel_channels"] = all_channels
                await ctx.reply(embed=self.bot.create_completed_embed("User Added!",
                                                                      "User {} has been added to {}.".format(
                                                                          mcuuid.api.GetPlayerData(uuid).username,
                                                                          channel.mention)))

    async def remove(self, ctx, username: str):
        uuid = await self.uuid_from_identifier(ctx, username)
        if uuid is None:
            return
        all_channels = self.data["hypixel_channels"]
        for channel_id in all_channels.keys():
            channel = self.bot.get_channel(int(channel_id))
            if uuid in self.data["hypixel_channels"][channel_id]:
                all_channels[channel_id].remove(uuid)
                self.data["hypixel_channels"] = all_channels
                await ctx.reply(embed=self.bot.create_completed_embed("User Removed!",
                                                                      "User {} has been removed from {}.".format(
                                                                          mcuuid.api.GetPlayerData(uuid).username,
                                                                          channel.mention)))




def setup(bot):
    cog = Hypixel(bot)
    bot.add_cog(cog)
