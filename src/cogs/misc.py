import datetime
from typing import Optional

import discord
import psutil
import webcolors
from discord.ext import commands, tasks

from main import UtilsBot
from src.checks.role_check import is_staff, is_high_staff
from src.checks.user_check import is_owner
from src.helpers.storage_helper import DataHelper
from src.storage import config


def convert_colour(input_colour):
    input_colour = input_colour.strip('#')
    try:
        colour = input_colour
        int(colour, 16)
        if len(colour) == 3:
            colour = webcolors.normalize_hex("#" + colour).strip('#')
        if len(colour) == 6:
            return discord.Colour.from_rgb(int(colour[:2], 16), int(colour[2:4], 16), int(colour[4:6], 16))
        else:
            raise commands.BadArgument
    except ValueError:
        try:
            return discord.Colour.from_rgb(*(webcolors.name_to_rgb(input_colour.replace(" ", ""))))
        except ValueError:
            raise commands.BadArgument


class Misc(commands.Cog):
    def __init__(self, bot: UtilsBot):
        self.bot = bot
        self.current_presence = 0
        self.update_status.start()

    @commands.command(pass_context=True)
    @is_staff()
    async def embed(self, ctx, colour: Optional[convert_colour] = discord.Colour.default(),
                    title: str = '\u200b', description: str = '\u200b', *fields):
        embed = discord.Embed(colour=colour, title=title, description=description, timestamp=datetime.datetime.utcnow())
        embed.set_author(name=ctx.message.author.name, icon_url=ctx.message.author.avatar_url)
        if len(fields) % 2 != 0:
            await ctx.reply(embed=self.bot.create_error_embed("Fields were not even."))
            return
        for i in range(0, len(fields), 2):
            embed.add_field(name=fields[i], value=fields[i + 1], inline=False)
        await ctx.reply(embed=embed)
        await ctx.message.delete(delay=5)

    @commands.command(name="error_channel", description="Sets the bot error message channel for this guild.")
    @is_owner()
    async def error_channel(self, ctx, error_channel: discord.TextChannel):
        data = DataHelper()
        error_channels = data.get("guild_error_channels", {})
        error_channels[str(ctx.guild.id)] = error_channel.id
        data["guild_error_channels"] = error_channels

    # noinspection SpellCheckingInspection
    @commands.command(pass_context=True)
    async def ping(self, ctx):
        before = datetime.datetime.now()
        sent_message: discord.Message = await ctx.reply("Pong!")
        after = datetime.datetime.now()
        milliseconds_to_send = round((after - before).total_seconds() * 1000)
        message: discord.Message = ctx.message
        heartbeat_latency = round(self.bot.latency * 1000)
        total_latency = round((sent_message.created_at - message.created_at).total_seconds() * 1000)
        embed = discord.Embed(title="Latency (Ping) Report", timestamp=datetime.datetime.utcnow())
        embed.add_field(name="Ping to Discord", value="{}ms".format(milliseconds_to_send // 2), inline=False)
        embed.add_field(name="Me -> Discord -> Me (Heartbeat)",
                        value="{}ms".format(heartbeat_latency), inline=False)
        embed.add_field(name="Total time: Your message -> My reply",
                        value="{}ms".format(total_latency), inline=False)
        # epoch = datetime.datetime.utcfromtimestamp(0)
        # rx_from_epoch = round((message.created_at - epoch).total_seconds() * 1000)
        # tx_from_epoch = round((sent_message.created_at - epoch).total_seconds() * 1000)
        # embed.add_field(name="Received (millis)", value=str(rx_from_epoch))
        # embed.add_field(name="Sent (millis)", value=str(tx_from_epoch))
        # embed.add_field(name="Difference between (ms)", value=str(tx_from_epoch-rx_from_epoch))
        # embed.add_field(name="Received snowflake timestamp", value=str((message.id >> 22) + 1420070400000))
        # embed.add_field(name="Sent snowflake timestamp", value=str((sent_message.id >> 22) + 1420070400000))

        if total_latency < 75:
            embed.colour = discord.Colour.green()
        elif total_latency < 250:
            embed.colour = discord.Colour.orange()
        else:
            embed.colour = discord.Colour.red()

        await sent_message.edit(content="", embed=embed)

    @commands.command()
    @is_owner()
    async def oldest(self, ctx):
        current_member = 0
        if self.bot.latest_joins == {}:
            await self.bot.get_latest_joins()
        members = self.bot.latest_joins[ctx.guild.id]
        leader_board = ""
        for member in members:
            current_member += 1
            string_to_add = "{}: {} - {}\n".format(current_member, member.name,
                                                   member.joined_at.strftime("%Y-%m-%d %H:%M"))
            if len(leader_board + string_to_add) > 2048:
                break
            leader_board = leader_board + string_to_add
        embed = discord.Embed(title="First Join Leaderboard", colour=discord.Colour.green(), description=leader_board)
        await ctx.reply(embed=embed)

    @commands.command(pass_context=True)
    @is_high_staff()
    async def members(self, ctx):
        data = DataHelper()
        enabled = not data.get("members", False)
        data["members"] = enabled
        state = ("Disabled", "Enabled")[enabled]
        await ctx.reply(embed=self.bot.create_completed_embed("Member Count {}!".format(state),
                                                             f"Member count logging successfully {state.lower()}"))

    async def update_members_vc(self):
        users_vc: discord.VoiceChannel = self.bot.get_channel(727202196600651858)
        data = DataHelper()
        if data["members"]:
            guild_members = users_vc.guild.member_count
            await users_vc.edit(name="Total Users: {}".format(guild_members))

    async def on_member_change(self, member):
        print("processing member change")
        guild = member.guild
        if guild.id == config.guild_id:
            await self.update_members_vc()
        self.bot.latest_joins[guild.id] = await self.bot.get_sorted_members(guild)

    @commands.Cog.listener()
    async def on_member_join(self, member):
        await self.on_member_change(member)

    @commands.Cog.listener()
    async def on_member_remove(self, member):
        await self.on_member_change(member)

    @tasks.loop(seconds=30, count=None)
    async def update_status(self):
        memory = psutil.virtual_memory()
        used = memory.available // (1024 ** 3)
        total = memory.total // (1024 ** 3)
        possible_presences = ["Current CPU load: {}%!".format(psutil.cpu_percent(None)),
                              "Current RAM usage: {}GB/{}GB.".format(used, total),
                              "Total guild count: {}!".format(len(self.bot.guilds)),
                              "Owner: Thomas_Waffles#0001"]
        activity = discord.Game(name=possible_presences[self.current_presence])
        self.current_presence += 1
        if self.current_presence > len(possible_presences) - 1:
            self.current_presence = 0
        await self.bot.change_presence(status=discord.Status.online, activity=activity)


def setup(bot):
    cog = Misc(bot)
    bot.add_cog(cog)
