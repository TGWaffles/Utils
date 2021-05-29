import datetime

import aiohttp
import discord
import humanize as humanize
from discord.ext import commands

from main import UtilsBot
from src.storage.token import uptime_robot_api


class Meta(commands.Cog):
    def __init__(self, bot: UtilsBot):
        self.bot = bot

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

        if total_latency < 75:
            embed.colour = discord.Colour.green()
        elif total_latency < 250:
            embed.colour = discord.Colour.orange()
        else:
            embed.colour = discord.Colour.red()

        await sent_message.edit(content="", embed=embed)

    @staticmethod
    def get_last_event_time(monitor, last_online=False):
        if last_online:
            search_type = 2
        else:
            search_type = 1
        last_log = [x for x in monitor["logs"] if x.get("type") == search_type]
        if len(last_log) == 0:
            return datetime.datetime(1970, 1, 1)
        else:
            last_date = datetime.datetime.utcfromtimestamp(last_log[0]["datetime"])
            return last_date

    @commands.command()
    async def status(self, ctx):
        embed = discord.Embed(title="Current Service Status", url="https://utils.thom.club/status")
        url = "https://api.uptimerobot.com/v2/getMonitors"

        payload = f"api_key={uptime_robot_api}&format=json&logs=1&all_time_uptime_ratio=1"
        headers = {
            'content-type': "application/x-www-form-urlencoded",
            'cache-control': "no-cache"
        }
        offline_count = 0
        async with aiohttp.ClientSession() as session:
            async with session.post(url, data=payload, headers=headers) as request:
                returned_json = await request.json()
        for monitor in returned_json.get("monitors", []):
            monitor_info = ""
            if monitor["status"] > 7:
                offline_count += 1
                monitor_info += "**Offline**\n\n"
                online_search = True
                last_text = "Last Online: {}\n\nI have been down for: {}\n"
            else:
                monitor_info += "**Online**\n\n"
                online_search = False
                last_text = "Last Offline: {}\n\nI have been online for: {}\n"
            last_event = self.get_last_event_time(monitor, online_search)
            if last_event != datetime.datetime(1970, 1, 1):
                delta_since_last = datetime.datetime.now() - last_event
                last_text = last_text.format(last_event.strftime("%Y-%m-%d %H:%M UTC"),
                                             humanize.naturaldelta(delta_since_last))
            else:
                last_text = last_text.format("never", "all known history")
            monitor_info += last_text
            embed.add_field(name=monitor["friendly_name"], value=monitor_info, inline=False)
        if offline_count > 0:
            embed.colour = discord.Colour.red()
        else:
            embed.colour = discord.Colour.green()
        await ctx.reply(embed=embed)


def setup(bot):
    cog = Meta(bot)
    bot.add_cog(cog)
