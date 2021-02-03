import discord
import asyncio
import sys
import json
import os
import datetime
import subprocess

from pretty_help import PrettyHelp
from discord.ext import commands
from src.storage import config
from src.helpers.storage_helper import DataHelper
from traceback import format_exc
from src.storage.token import token  # token.py is just one variable - token = "token"


class UtilsBot(commands.Bot):
    def __init__(self):
        # Initialises the actual commands.Bot class
        intents = discord.Intents.all()
        intents.members = True
        super().__init__(command_prefix=config.bot_prefix, description=config.description,
                         loop=asyncio.new_event_loop(), intents=intents, case_insensitive=True,
                         help_command=PrettyHelp(color=discord.Colour.blue()))
        self.guild = None
        self.error_channel = None
        self.data = DataHelper()
        self.latest_joins = {}

    async def get_latest_joins(self):
        for guild in self.guilds:
            members = await self.get_sorted_members(guild)
            self.latest_joins[guild.id] = members

    async def get_sorted_members(self, guild):
        members = await guild.fetch_members(limit=None).flatten()
        if guild.id == config.monkey_guild_id:
            member_ids = [user.id for user in members]
            all_guilds = self.data.get("og_messages", {})
            og_messages = all_guilds.get(str(guild.id), {})
            for user_id in og_messages.keys():
                try:
                    member_object = members[member_ids.index(int(user_id))]
                    first_join = datetime.datetime.utcfromtimestamp(og_messages[user_id])
                    if first_join < member_object.joined_at:
                        member_object.joined_at = first_join
                        members[member_ids.index(int(user_id))] = member_object
                except (ValueError, IndexError):
                    pass
        members = [user for user in members if user.joined_at is not None]
        members.sort(key=lambda x: x.joined_at)
        return members

    # The following embeds are just to create embeds with the correct colour in fewer words.
    @staticmethod
    def create_error_embed(text):
        embed = discord.Embed(title="Error", description=text, colour=discord.Colour.red(),
                              timestamp=datetime.datetime.utcnow())
        return embed

    @staticmethod
    def create_processing_embed(title, text):
        embed = discord.Embed(title=title, description=text, colour=discord.Colour.dark_orange(),
                              timestamp=datetime.datetime.utcnow())
        return embed

    @staticmethod
    def create_completed_embed(title, text):
        embed = discord.Embed(title=title, description=text, colour=discord.Colour.green(),
                              timestamp=datetime.datetime.utcnow())
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
    data = DataHelper()

    @bot.event
    async def on_ready():
        print("Ready!")
        bot.guild = bot.get_guild(config.monkey_guild_id)
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
        await bot.get_latest_joins()

    # noinspection PyUnusedLocal
    @bot.event
    async def on_error(method, *args, **kwargs):
        try:
            embed = discord.Embed(title="MonkeyUtils experienced an error when running.", colour=discord.Colour.red())
            embed.description = format_exc()[:2000]
            await bot.error_channel.send(embed=embed)
            # bot.restart()
        except Exception as e:
            print("Error in sending error to discord. Error was {}".format(format_exc()))
            print("Error sending to discord was {}".format(e))

    @bot.event
    async def on_command_error(ctx, error):
        if isinstance(error, commands.CommandNotFound) or isinstance(error, commands.DisabledCommand):
            return
        if isinstance(error, commands.CheckFailure):
            await ctx.send(embed=bot.create_error_embed("You don't have permission to do that, {}.".
                                                        format(ctx.message.author.mention)))
            return
        try:
            embed = discord.Embed(title="MonkeyUtils experienced an error in a command.", colour=discord.Colour.red())
            embed.description = format_exc()[:2000]
            embed.add_field(name="Command passed error", value=error)
            embed.add_field(name="Context", value=ctx.message.content)
            guild_error_channel_id = data.get("guild_error_channels", {}).get(str(ctx.guild.id), 795057163768037376)
            error_channel = bot.get_channel(guild_error_channel_id)
            await error_channel.send(embed=embed)
            # bot.restart()
        except Exception as e:
            print("Error in sending error to discord. Error was {}".format(error))
            print("Error sending to discord was {}".format(e))

    return bot


if __name__ == '__main__':
    utils_bot = get_bot()
    utils_bot.run(token)
