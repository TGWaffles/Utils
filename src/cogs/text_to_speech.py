import discord
import asyncio
import concurrent.futures
import pydub
import os

from pydub import effects
from io import BytesIO
from discord.ext import commands
from main import UtilsBot
from src.checks.role_check import is_high_staff
from src.checks.custom_check import speak_changer_check
from src.storage import messages
from src.helpers.storage_helper import DataHelper
from src.helpers.tts_helper import get_speak_file
from typing import Optional
from functools import partial


class TTS(commands.Cog):
    def __init__(self, bot: UtilsBot):
        self.bot = bot
        self.data = DataHelper()
        self.index_num = 0

    @commands.command(pass_context=True)
    @speak_changer_check()
    async def disconnect(self, ctx):
        voice_clients = [x for x in self.bot.voice_clients if x.guild.id == ctx.guild.id]
        if len(voice_clients) == 0:
            await ctx.send(messages.no_voice_clients)
            return
        try:
            await voice_clients[0].disconnect()
        except Exception as e:
            await ctx.send(embed=self.bot.create_error_embed("Error disconnecting from vc: {}".format(e)))
            return
        await ctx.send(embed=self.bot.create_completed_embed("Disconnect success.", "Disconnected from voice."))

    @commands.command(pass_context=True, name="speak_perms",
                      description="Gives other people access to the !speak command.")
    @is_high_staff()
    async def speak_perms(self, ctx, member: discord.Member):
        all_guilds = self.data.get("speak_changer", {})
        changer_list = all_guilds.get(str(ctx.guild.id), [])
        if member.id in changer_list:
            changer_list.remove(member.id)
            await ctx.send(embed=self.bot.create_completed_embed("Perms Revoked",
                                                                 f"Revoked {member.display_name}'s permissions!"))
        else:
            changer_list.append(member.id)
            await ctx.send(embed=self.bot.create_completed_embed("Perms Granted",
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
            await ctx.send(embed=self.bot.create_completed_embed("Disabled TTS", f"Removed {member.display_name} from "
                                                                                 f"the TTS list"))
        else:
            speaking_list.append(member.id)
            await ctx.send(embed=self.bot.create_completed_embed("Enabled TTS", f"Added {member.display_name} to the "
                                                                                f"TTS list."))
        all_guilds[str(ctx.guild.id)] = speaking_list
        self.data["speaking"] = all_guilds

    @commands.command(pass_context=True)
    @speak_changer_check()
    async def lang(self, ctx, new_lang: str):
        server_languages = self.data.get("server_languages", {})
        server_languages[ctx.guild.id] = new_lang
        self.data["server_languages"] = server_languages
        print(self.data["server_languages"])
        await ctx.send(embed=self.bot.create_completed_embed("Language changed!",
                                                             f"Changed voice language to {new_lang}"))

    async def speak_message(self, message):
        member = message.author
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
        lang = server_languages.get(str(message.guild.id), "en")
        with concurrent.futures.ProcessPoolExecutor() as pool:
            output = await self.bot.loop.run_in_executor(pool, partial(get_speak_file, message.clean_content, lang))
        while voice_client.is_playing():
            await asyncio.sleep(0.1)
        try:
            voice_client.play(discord.PCMAudio(output))
        except discord.errors.ClientException:
            pass
        while voice_client.is_playing():
            await asyncio.sleep(0.5)

    @commands.Cog.listener()
    async def on_message(self, message):
        member = message.author
        if member.id not in self.data.get("speaking", []):
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
