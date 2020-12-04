import discord
import asyncio
import sys
import json
import os
import subprocess

from discord.ext import commands
from src.storage import config
from traceback import format_exc
from src.storage.token import token  # token.py is just one variable - token = "token"


class UtilsBot(commands.Bot):
    def __init__(self):
        # Initialises the actual commands.Bot class
        super().__init__(command_prefix=config.bot_prefix, description=config.description,
                         loop=asyncio.new_event_loop())
        self.guild = None
        self.error_channel = None

    # The following embeds are just to create embeds with the correct colour in fewer words.
    @staticmethod
    def create_error_embed(text):
        embed = discord.Embed(title="Error", description=text, colour=discord.Colour.red())
        return embed

    @staticmethod
    def create_processing_embed(title, text):
        embed = discord.Embed(title=title, description=text, colour=discord.Colour.dark_orange())
        return embed

    @staticmethod
    def create_completed_embed(title, text):
        embed = discord.Embed(title=title, description=text, colour=discord.Colour.green())
        return embed

    @staticmethod
    def restart():
        sys.exit(1)

    @staticmethod
    def completed_restart_write(channel_id, message_id, title, text):
        with open("restart_info.json", 'w') as file:
            file.write(json.dumps([channel_id, message_id, title, text, config.version_number]))


def get_bot():
    bot = UtilsBot()

    @bot.event
    async def on_ready():
        print("Ready!")
        bot.guild = bot.get_guild(config.guild_id)
        bot.error_channel = bot.get_channel(config.error_channel_id)
        for extension_name in config.extensions:
            print("Loading cog named {}...".format(extension_name))
            bot.load_extension("src.cogs.{}".format(extension_name))
            print("Loaded cog {}!".format(extension_name))
        if os.path.exists("restart_info.json"):
            with open("restart_info.json", 'r') as file:
                channel_id, message_id, title, text, old_version_num = json.loads(file.read())
            original_msg = await bot.get_channel(channel_id).fetch_message(message_id)
            embed = bot.create_completed_embed(title, text)
            embed.add_field(name="New Version: {}".format(config.version_number),
                            value="Previous Version: {}".format(old_version_num))
            last_commit_message = subprocess.check_output(["git", "log", "-1", "--pretty=%s"]).decode("utf-8").strip()
            embed.set_footer(text=last_commit_message)
            await original_msg.edit(embed=embed)
            os.remove("restart_info.json")

    # noinspection PyUnusedLocal
    @bot.event
    async def on_error(method, *args, **kwargs):
        try:
            embed = discord.Embed(title="MonkeyUtils experienced an error when running.", colour=discord.Colour.red())
            embed.description = format_exc()[:2000]
            await bot.error_channel.send(embed=embed)
            bot.restart()
        except Exception as e:
            print("Error in sending error to discord. Error was {}".format(format_exc()))
            print("Error sending to discord was {}".format(e))

    @bot.event
    async def on_command_error(ctx, error):
        if isinstance(error, commands.CommandNotFound) or isinstance(error, commands.DisabledCommand):
            return
        try:
            embed = discord.Embed(title="MonkeyUtils experienced an error in a command.", colour=discord.Colour.red())
            embed.description = format_exc()[:2000]
            embed.add_field(name="Command passed error", value=error)
            embed.add_field(name="Context", value=ctx.message.content)
            await bot.error_channel.send(embed=embed)
            bot.restart()
        except Exception as e:
            print("Error in sending error to discord. Error was {}".format(format_exc()))
            print("Error sending to discord was {}".format(e))

    return bot


if __name__ == '__main__':
    utils_bot = get_bot()
    utils_bot.run(token)
