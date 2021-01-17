import asyncio
import concurrent.futures
from functools import partial
from typing import Optional

import discord
import gtts.lang
from discord.ext import commands

from main import UtilsBot
from src.checks.custom_check import speak_changer_check
from src.checks.role_check import is_high_staff
from src.helpers import chris_tts_helper
from src.helpers.storage_helper import DataHelper
from src.helpers.tts_helper import get_speak_file
from src.storage import messages
from src.storage import config


class TTS(commands.Cog):
    def __init__(self, bot: UtilsBot):
        self.bot = bot
        self.data = DataHelper()
        self.index_num = 0
        self.bot.loop.create_task(chris_tts_helper.start_server(self))

    @commands.command(pass_context=True)
    @speak_changer_check()
    async def disconnect(self, ctx):
        voice_clients = [x for x in self.bot.voice_clients if x.guild.id == ctx.guild.id]
        if len(voice_clients) == 0:
            await ctx.reply(messages.no_voice_clients)
            return
        try:
            await voice_clients[0].disconnect()
        except Exception as e:
            await ctx.reply(embed=self.bot.create_error_embed("Error disconnecting from vc: {}".format(e)))
            return
        await ctx.reply(embed=self.bot.create_completed_embed("Disconnect success.", "Disconnected from voice."))

    @commands.command(pass_context=True, name="speak_perms",
                      description="Gives other people access to the !speak command.")
    @is_high_staff()
    async def speak_perms(self, ctx, member: discord.Member):
        all_guilds = self.data.get("speak_changer", {})
        changer_list = all_guilds.get(str(ctx.guild.id), [])
        if member.id in changer_list:
            changer_list.remove(member.id)
            await ctx.reply(embed=self.bot.create_completed_embed("Perms Revoked",
                                                                  f"Revoked {member.display_name}'s permissions!"))
        else:
            changer_list.append(member.id)
            await ctx.reply(embed=self.bot.create_completed_embed("Perms Granted",
                                                                  f"Given {member.display_name} permissions!"))
        all_guilds[str(ctx.guild.id)] = changer_list
        self.data["speak_changer"] = all_guilds

    @commands.command(pass_context=True, name="speak", description="Adds/removes a user to the TTS list.")
    @speak_changer_check()
    async def speak(self, ctx, member: Optional[discord.Member] = None):
        if member is None:
            member = ctx.author
        all_guilds = self.data.get("speaking", {})
        speaking_list = all_guilds.get(str(ctx.guild.id), [])
        if member.id in speaking_list:
            speaking_list.remove(member.id)
            await ctx.reply(embed=self.bot.create_completed_embed("Disabled TTS", f"Removed {member.display_name} from "
                                                                                  f"the TTS list"))
        else:
            speaking_list.append(member.id)
            await ctx.reply(embed=self.bot.create_completed_embed("Enabled TTS", f"Added {member.display_name} to the "
                                                                                 f"TTS list."))
        all_guilds[str(ctx.guild.id)] = speaking_list
        self.data["speaking"] = all_guilds

    @commands.command(pass_context=True)
    @speak_changer_check()
    async def speed(self, ctx, new_speed: float):
        if new_speed < 0:
            await ctx.reply(embed=self.bot.create_error_embed("A speed less than 0 makes no sense."))
        all_guilds = self.data.get("speak_speeds", {})
        all_guilds[str(ctx.guild.id)] = new_speed
        self.data["speak_speeds"] = all_guilds
        await ctx.reply(embed=self.bot.create_completed_embed("Speed Changed!", "New speed in here is {}. "
                                                                                "(default 1.0)".format(new_speed)))

    @commands.command(pass_context=True)
    @speak_changer_check()
    async def lang(self, ctx, new_lang: str):
        new_lang = new_lang.lower()
        if new_lang not in gtts.lang.tts_langs().keys():
            lang_embed = discord.Embed(title="Invalid Language", colour=discord.Colour.red())
            description = "**Available Languages**"
            field_to_add_to = 0
            left_field_text = ""
            middle_field_text = ""
            right_field_text = ""
            for short, long in gtts.lang.tts_langs().items():
                if field_to_add_to == 0:
                    left_field_text += "**{}** - {}\n".format(short, long)
                elif field_to_add_to == 1:
                    middle_field_text += "**{}** - {}\n".format(short, long)
                else:
                    right_field_text += "**{}** - {}\n".format(short, long)
                    field_to_add_to = -1
                field_to_add_to += 1
            lang_embed.description = description
            lang_embed.add_field(name='\u200b', value=left_field_text)
            lang_embed.add_field(name='\u200b', value=middle_field_text)
            lang_embed.add_field(name='\u200b', value=right_field_text)
            await ctx.reply(embed=lang_embed)
            return
        server_languages = self.data.get("server_languages", {})
        server_languages[ctx.guild.id] = new_lang
        self.data["server_languages"] = server_languages
        await ctx.reply(embed=self.bot.create_completed_embed("Language changed!",
                                                              f"Changed voice language to {new_lang}"))

    @commands.command(pass_context=True)
    @speak_changer_check()
    async def speakers(self, ctx):
        all_guilds = self.data.get("speaking", {})
        speaking_list = all_guilds.get(str(ctx.guild.id), [])
        all_perms = self.data.get("speak_changer", {})
        guild_perms = all_perms.get(str(ctx.guild.id), [])
        embed = discord.Embed(title="Speaking Users", description="", colour=discord.Colour.green())
        for member_id in speaking_list:
            try:
                member = ctx.guild.get_member(member_id)
                if (member.guild_permissions.administrator or
                        member_id in guild_perms or ctx.author.id == config.owner_id):
                    embed.description += "{} (has permission to add others)\n".format(member.mention)
                else:
                    embed.description += "{}\n".format(member.mention)
            except AttributeError:
                pass
        await ctx.reply(embed=embed)

    @commands.command(pass_context=True)
    @is_high_staff()
    async def reset_speakers(self, ctx):
        all_guilds = self.data.get("speaking", {})
        all_guilds[str(ctx.guild.id)] = []
        self.data["speaking"] = all_guilds
        await ctx.reply(self.bot.create_completed_embed("Reset All Speakers", "No one has speak enabled."))

    async def speak_message(self, message):
        member = message.author
        await self.speak_content_in_channel(member, message.clean_content)

    async def speak_id_content(self, member_id, content):
        member_id = int(member_id)
        for guild in self.bot.guilds:
            try:
                member = await guild.fetch_member(member_id)
            except discord.errors.NotFound:
                continue
            speak_return = await self.speak_content_in_channel(member, content)
            if speak_return is not None:
                return

    async def speak_content_in_channel(self, member, content):
        if member.voice is None or member.voice.channel is None:
            return
        voice_channel = member.voice.channel
        voices_in_guild = [x for x in self.bot.voice_clients if x.guild == voice_channel.guild]
        if len(voices_in_guild) > 0:
            voice_client = voices_in_guild[0]
            if voice_client.channel != voice_channel:
                await voice_client.disconnect()
                voice_client = await voice_channel.connect()
        else:
            voice_client = await voice_channel.connect()
        server_languages = self.data.get("server_languages", {})
        lang = server_languages.get(str(voice_channel.guild.id), "en")
        speed = self.data.get("speak_speeds", {}).get(str(voice_channel.guild.id), 1.0)
        with concurrent.futures.ProcessPoolExecutor() as pool:
            output = await self.bot.loop.run_in_executor(pool, partial(get_speak_file, content,
                                                                       lang, speed))
        while voice_client.is_playing():
            await asyncio.sleep(0.1)
        try:
            voice_client.play(discord.PCMAudio(output))
        except discord.errors.ClientException:
            pass
        while voice_client.is_playing():
            await asyncio.sleep(0.5)
        return True

    @commands.Cog.listener()
    async def on_message(self, message):
        member = message.author
        try:
            if member.id == self.bot.user.id or member.guild is None:
                return
        except AttributeError:
            return
        all_guilds = self.data.get("speaking", {})
        speaking = all_guilds.get(str(message.guild.id), [])
        if member.id not in speaking:
            return
        if message.content.startswith("!") or message.content.startswith("~"):
            return
        await self.speak_message(message)

    @commands.Cog.listener()
    async def on_voice_state_update(self, _, before, after):
        if before.channel is not None and after.channel is None:
            if len(before.channel.members) == 1 and before.channel.members[0].id == self.bot.user.id:
                voices_in_guild = [x for x in self.bot.voice_clients if x.guild == before.channel.guild]
                for voice_client in voices_in_guild:
                    await voice_client.disconnect()


def setup(bot):
    cog = TTS(bot)
    bot.add_cog(cog)
