import asyncio
import datetime
import json
import os
import subprocess
import sys
import time
from traceback import format_exc, print_tb
from typing import Union

import discord
import pymongo
from discord.ext import commands
from discord.ext.commands.core import _convert_to_bool

from src.checks.message_check import check_reply, question_check
from src.helpers.help import UtilsHelp
from src.helpers.mongo_helper import MongoDB
from src.helpers.storage_helper import DataHelper
from src.storage import config
from src.storage.token import token  # token.py is just one variable - token = "token"


class UtilsBot(commands.Bot):
    def __init__(self):
        # Initialises the actual commands.Bot class
        intents = discord.Intents.all()
        intents.members = True
        # help_command = PrettyHelp(color=discord.Colour.blue())
        # help_command.paginator.char_limit = 2000
        super().__init__(command_prefix=self.determine_prefix, description=config.description,
                         loop=asyncio.get_event_loop(), intents=intents, case_insensitive=True)
        self.help_command = UtilsHelp()
        self.guild = None
        self.error_channel = None
        self.data = DataHelper()
        self.database_handler = None
        self.latest_joins = {}
        self.restart_event: Union[asyncio.Event, None] = None
        self.mongo: Union[MongoDB, None] = None
        self.restart_waiter_lock = asyncio.Lock()
        self.restart_waiters = 0

    async def get_guild_prefix(self, guild: discord.Guild):
        if self.mongo is None:
            return ""
        guild_document = await self.mongo.find_by_id(self.mongo.discord_db.guilds, guild.id)
        return guild_document.get("prefix", "")

    async def determine_prefix(self, bot, message):
        if not hasattr(message, "guild") or message.guild is None:
            return commands.when_mentioned_or(config.bot_prefix, "u" + config.bot_prefix)(bot, message)
        if self.mongo is None:
            return f"u{config.bot_prefix}"
        guild_document = await self.mongo.find_by_id(self.mongo.discord_db.guilds, message.guild.id)
        if guild_document is None or guild_document.get("prefix") is None:
            music_cog: commands.Cog = self.get_cog("Music")
            if music_cog is not None:
                for command in music_cog.get_commands():
                    possible_command = [command.name] + command.aliases
                    possible_command = [config.bot_prefix + x for x in possible_command]
                    if message.content.split(" ")[0] in possible_command:
                        return commands.when_mentioned_or("u" + config.bot_prefix)(bot, message)
            return commands.when_mentioned_or(config.bot_prefix, "u" + config.bot_prefix)(bot, message)
        else:
            guild_prefix = guild_document.get("prefix")
            return commands.when_mentioned_or(guild_prefix, "u" + config.bot_prefix)(bot, message)

    async def get_latest_joins(self):
        for guild in self.guilds:
            members = await self.get_sorted_members(guild)
            self.latest_joins[guild.id] = members

    async def get_sorted_members(self, guild):
        members = await guild.fetch_members(limit=None).flatten()
        members = [member for member in members if not member.bot]
        sorting_members = {member: (member,
                                    member.joined_at.replace(tzinfo=datetime.timezone.utc)) for member in members}
        for member in members:
            earliest_message = await self.mongo.discord_db.messages.find_one({"user_id": member.id,
                                                                              "guild_id": guild.id},
                                                                             sort=[("created_at", pymongo.ASCENDING)])
            if earliest_message is not None:
                message_time = earliest_message.get("created_at").replace(tzinfo=datetime.timezone.utc)
                if message_time < member.joined_at.replace(tzinfo=datetime.timezone.utc):
                    sorting_members[member] = (member, message_time)
                    member.joined_at = message_time
        members = list(sorting_members.values())
        members.sort(key=lambda x: x[1])
        members = [member[0] for member in members]
        members = [user for user in members if user.joined_at is not None]
        return members

    async def ask_boolean(self, to_reply_to: Union[discord.Message, discord.abc.Messageable], user: discord.User,
                          question: Union[str, discord.Embed]):
        if isinstance(to_reply_to, discord.Message):
            if isinstance(question, str):
                sent_message = await to_reply_to.reply(question)
            else:
                sent_message = await to_reply_to.reply(embed=question)
        else:
            if isinstance(question, str):
                sent_message = await to_reply_to.send(question)
            else:
                sent_message = await to_reply_to.send(embed=question)
        try:
            replied_message = await self.wait_for("message", check=check_reply(user), timeout=15.0)
            if not _convert_to_bool(replied_message.content):
                return False
            return sent_message
        except asyncio.TimeoutError:
            if isinstance(question, str):
                await sent_message.edit(content="No valid response detected in time, or explicit 'no' detected. "
                                                "Request cancelled.")
            else:
                await sent_message.edit(embed=self.create_error_embed("No valid response detected in time, or explicit "
                                                                      "'no' detected. "
                                                                      "Request cancelled."))
            return False

    async def ask_question(self, ctx, question=None):
        if question is not None:
            await ctx.reply(embed=self.create_completed_embed("Search Query", question))
        try:
            replied_message = await self.wait_for("message", check=question_check(ctx.author), timeout=30.0)
        except asyncio.TimeoutError:
            await ctx.reply(embed=self.create_error_embed("You took too long to respond! Search cancelled."))
            ctx.kwargs["resolved"] = True
            raise asyncio.TimeoutError()
        return replied_message.content

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

    @bot.event
    async def on_ready():
        print("Ready!")
        for extension_name, extension in bot.extensions.items():
            bot.unload_extension(extension_name)
        bot.mongo = MongoDB()
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
            print(format_exc())
            await bot.error_channel.send(embed=embed)
            # bot.restart()
        except Exception as e:
            print("Error in sending error to discord. Error was {}".format(format_exc()))
            print("Error sending to discord was {}".format(e))

    @bot.event
    async def on_command_error(ctx: commands.Context, error: commands.CommandError):
        if ctx.kwargs.get("resolved", False):
            return
        if isinstance(error, commands.CommandInvokeError):
            if isinstance(error.original, discord.errors.Forbidden):
                await ctx.author.send(embed=bot.create_error_embed("You ran the command `{}`, but I don't "
                                                                   "have permission to send "
                                                                   "messages in that channel!".format(ctx.command)))
                return
            print(type(error.original))
        if isinstance(error, commands.BotMissingPermissions):
            missing = [perm.replace('_', ' ').replace('guild', 'server').title() for perm in error.missing_perms]

            if len(missing) > 2:
                perms_formatted = '{}, and {}'.format(", ".join(missing[:-1]), missing[-1])
            else:
                perms_formatted = ' and '.join(missing)
            try:
                await ctx.reply(
                    f"In order to run these commands, I need the following permission(s): {perms_formatted}")
            except discord.errors.Forbidden:
                await ctx.author.send(embed=bot.create_error_embed("You ran the command `{}`, but I don't "
                                                                   "have permission to send "
                                                                   "messages in that channel!".format(ctx.command)))
            return

        if isinstance(error, commands.CommandNotFound) or isinstance(error, commands.DisabledCommand):
            return
        if isinstance(error, commands.CheckFailure):
            try:
                await ctx.send(embed=bot.create_error_embed("You don't have permission to do that, {}.".
                                                            format(ctx.message.author.mention)))
                return
            except discord.errors.Forbidden:
                await ctx.author.send(embed=bot.create_error_embed("You ran the command `{}`, but I don't "
                                                                   "have permission to send "
                                                                   "messages in that channel!".format(ctx.command)))
                return
        try:
            embed = discord.Embed(title="MonkeyUtils experienced an error in a command.", colour=discord.Colour.red())
            embed.description = format_exc()[:2000]
            embed.add_field(name="Command passed error", value=str(error))
            if ctx.message.application is not None and ctx.message.application.get("original_content") is not None:
                embed.add_field(name="Context", value=ctx.message.application.get("original_content"))
            else:
                embed.add_field(name="Context", value=ctx.message.content)
            print_tb(error.__traceback__)
            if hasattr(error, "original"):
                print_tb(error.original.__traceback__)
            guild_error_channel_id = await bot.mongo.discord_db.channels.find_one({"guild_id": ctx.guild.id,
                                                                                   "error_channel": True})
            if guild_error_channel_id is None:
                guild_error_channel_id = config.error_channel_id
            else:
                guild_error_channel_id = guild_error_channel_id.get("_id", None)
            error_channel = bot.get_channel(guild_error_channel_id)
            if error_channel is None:
                error_channel = bot.get_channel(config.error_channel_id)
            await error_channel.send(embed=embed)
            try:
                await ctx.reply(embed=embed)
            except discord.errors.HTTPException as http_e:
                if http_e.code == 400:
                    await ctx.send(embed=bot.create_error_embed("The original message was deleted! "
                                                                "Could not reply with error. Please don't run commands "
                                                                "in a channel that auto-deletes."))
                    await ctx.send(embed=embed)
                print(f"{http_e.code = }, {http_e.args = }")

            # bot.restart()
        except Exception as e:
            print("Error in sending error to discord. Error was {}".format(error))
            print("Error sending to discord was {}".format(e))

    return bot


if __name__ == '__main__':
    utils_bot = get_bot()
    try:
        utils_bot.run(token)
    except discord.errors.LoginFailure:
        time.sleep(18000)
        exit()
    except discord.errors.ConnectionClosed:
        if not asyncio.get_event_loop().is_closed():
            asyncio.get_event_loop().close()
        print("Connection Closed, exiting...")
        exit()
