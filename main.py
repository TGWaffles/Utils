import discord
import asyncio
import config
import sys

from discord.ext import commands
from traceback import format_exc
from token import token  # token.py is just one variable - token = "token"


class UtilsBot(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix=config.bot_prefix, description=config.description,
                         loop=asyncio.new_event_loop())
        self.guild = None

    @staticmethod
    def create_error_embed(text):
        embed = discord.Embed(title="Error", description=text, colour=discord.Colour.red())
        return embed

    @staticmethod
    def restart():
        sys.exit(1)


def get_bot():
    bot = UtilsBot()

    @bot.event
    async def on_ready():
        for extension_name in config.extensions:
            print("Loading cog named {}...".format(extension_name))
            bot.load_extension(extension_name)
            print("Loaded cog {}!".format(extension_name))
        bot.guild = bot.get_guild(config.guild_id)

    # noinspection PyUnusedLocal
    @bot.event
    async def on_error(method, *args, **kwargs):
        try:
            error_channel = bot.get_channel(config.error_channel_id)
            embed = discord.Embed(title="MonkeyUtils experienced an error when running.", colour=discord.Colour.red())
            embed.description = format_exc()[:2000]
            await error_channel.send(embed=embed)
            bot.restart()
        except Exception as e:
            print("Error in sending error to discord. Error was {}".format(format_exc()))
            print("Error sending to discord was {}".format(e))

    @bot.event
    async def on_command_error(ctx, error):
        try:
            error_channel = bot.get_channel(config.error_channel_id)
            embed = discord.Embed(title="MonkeyUtils experienced an error in a command.", colour=discord.Colour.red())
            embed.description = format_exc()[:2000]
            embed.add_field(name="Command passed error", value=error)
            embed.add_field(name="Context", value=ctx)
            await error_channel.send(embed=embed)
            bot.restart()
        except Exception as e:
            print("Error in sending error to discord. Error was {}".format(format_exc()))
            print("Error sending to discord was {}".format(e))

    return bot


if __name__ == '__main__':
    utils_bot = get_bot()
    utils_bot.run(token)
