import discord
import datetime

from discord.ext import commands
from src.main import UtilsBot


class Misc:
    def __init__(self, bot: UtilsBot):
        self.bot = bot

    @commands.command(pass_context=True)
    async def ping(self, ctx):
        time_now = datetime.datetime.now()
        message: discord.Message = ctx.message
        receive_message_delay = (time_now - message.created_at).microseconds // 1000
        time_before = datetime.datetime.now()
        sent_message: discord.Message = await ctx.send("Pong!")
        send_message_delay = (sent_message.created_at - time_before).microseconds // 1000
        heartbeat_latency = self.bot.latency * 1000
        total_latency = (sent_message.created_at - message.created_at).microseconds // 1000
        embed = discord.Embed(title="Latency (Ping) Report")
        embed.add_field(name="Time between your message being received by discord vs time I receive it",
                        value="{}ms".format(receive_message_delay))
        embed.add_field(name="Time it took for discord to receive my pong", value="{}ms".format(send_message_delay))
        embed.add_field(name="Heartbeat latency (my pure time taken for any response from discord)",
                        value="{}ms".format(heartbeat_latency))
        embed.add_field(name="Total latency from your message time to my message time",
                        value="{}ms".format(total_latency))
        await sent_message.edit(content="", embed=embed)


def setup(bot):
    cog = Misc(bot)
    bot.add_cog(cog)
