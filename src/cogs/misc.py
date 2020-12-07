import discord
import datetime

from discord.ext import commands
from main import UtilsBot
from src.checks.user_check import is_owner


class Misc(commands.Cog):
    def __init__(self, bot: UtilsBot):
        self.bot = bot

    # noinspection SpellCheckingInspection
    @commands.command(pass_context=True)
    async def ping(self, ctx):
        before = datetime.datetime.now()
        sent_message: discord.Message = await ctx.send("Pong!")
        after = datetime.datetime.now()
        milliseconds_to_send = round((after - before).total_seconds() * 1000)
        message: discord.Message = ctx.message
        heartbeat_latency = round(self.bot.latency * 1000)
        total_latency = round((sent_message.created_at - message.created_at).total_seconds() * 1000)
        embed = discord.Embed(title="Latency (Ping) Report")
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

    @commands.command(pass_context=True)
    @is_owner()
    async def members(self, ctx):
        temp_text = ""
        for member in ctx.message.guild.members:
            if len(temp_text) < 1900:
                temp_text += member.displayname + "\n"
            else:
                await ctx.send(temp_text)
                temp_text = ""



def setup(bot):
    cog = Misc(bot)
    bot.add_cog(cog)
