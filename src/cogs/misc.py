import discord
import datetime
import webcolors

from discord.ext import commands
from typing import Optional
from main import UtilsBot
from src.checks.user_check import is_owner
from src.checks.role_check import is_staff

def convert_colour(colour):
    try:
        colour = colour.strip('#')
        int(colour, 16)
        print(21)
        if len(colour) == 3:
            embed_colour = discord.Colour.from_rgb(int(colour[0], 16), int(colour[1], 16), int(colour[2], 16))
        elif len(colour) == 6:
            print(25)
            embed_colour = discord.Colour.from_rgb(int(colour[:2], 16), int(colour[2:4], 16), int(colour[4:6], 16))
            print(27)
        else:
            raise commands.BadArgument
    except ValueError:
        try:
            embed_colour = discord.Colour.from_rgb(*(webcolors.name_to_rgb(colour.replace(" ", ""))))
        except ValueError:
            raise commands.BadArgument
    return embed_colour

class Misc(commands.Cog):
    def __init__(self, bot: UtilsBot):
        self.bot = bot
        
    @commands.command(pass_context=True)
    @is_staff()
    async def embed(self, ctx, colour: Optional[convert_colour] = "000000", title: str = '\u200b', description: str = '\u200b', *fields):
        embed = discord.Embed(colour=colour, title=title, description=description)
        embed.set_author(name=ctx.message.author.name, icon_url=ctx.message.author.avatar_url)
        if len(fields) % 2 != 0:
            await ctx.send(embed=self.bot.create_error_embed("Fields were not even."))
            return
        for i in range(0, len(fields), 2):
            embed.add_field(name=fields[i], value=fields[i+1], inline=False)
        await ctx.send(embed=embed)
        await ctx.message.delete(delay=5)

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



def setup(bot):
    cog = Misc(bot)
    bot.add_cog(cog)
