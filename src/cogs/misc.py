import discord
import datetime

from discord.ext import commands
from main import UtilsBot


class Misc(commands.Cog):
    def __init__(self, bot: UtilsBot):
        self.bot = bot

    @commands.command(pass_context=True)
    async def ping(self, ctx):
        before = datetime.datetime.now()
        sent_message: discord.Message = await ctx.send("Pong!")
        after = datetime.datetime.now()
        milliseconds_to_send = round((after - before).total_seconds() * 1000)
        message: discord.Message = ctx.message
        heartbeat_latency = round(self.bot.latency * 1000)
        total_latency = (sent_message.created_at - message.created_at).microseconds // 1000
        embed = discord.Embed(title="Latency (Ping) Report")
        embed.add_field(name="Ping to Discord", value="{}ms".format(milliseconds_to_send // 2), inline=False)
        embed.add_field(name="Me -> Discord -> Me (Heartbeat)",
                        value="{}ms".format(heartbeat_latency), inline=False)
        embed.add_field(name="Total time: Your message -> My reply",
                        value="{}ms".format(total_latency), inline=False)

        await sent_message.edit(content="", embed=embed)


def setup(bot):
    cog = Misc(bot)
    bot.add_cog(cog)
