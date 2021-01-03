import discord
import asyncio
import pydub
import os

from pydub import effects
from gtts import gTTS
from discord.ext import commands
from main import UtilsBot
from src.checks.role_check import is_high_staff
from src.checks.custom_check import speak_changer_check
from src.storage import messages
from src.helpers.storage_helper import DataHelper
from typing import Optional


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
        changer_list = self.data.get("speak_changer", [])
        if member.id in changer_list:
            changer_list.remove(member.id)
            await ctx.send(embed=self.bot.create_completed_embed("Perms Revoked",
                                                                 f"Revoked {member.display_name}'s permissions!"))
        else:
            changer_list.append(member.id)
            await ctx.send(embed=self.bot.create_completed_embed("Perms Granted",
                                                                 f"Given {member.display_name} permissions!"))
        self.data["speak_changer"] = changer_list

    @commands.command(pass_context=True, name="speak", description="Adds/removes a user to the TTS list.")
    @speak_changer_check()
    async def speak(self, ctx, member: Optional[discord.Member] = None):
        if member is None:
            member = ctx.author
        speaking_list = self.data.get("speaking", [])
        if member.id in speaking_list:
            speaking_list.remove(member.id)
            await ctx.send(embed=self.bot.create_completed_embed("Disabled TTS", f"Removed {member.display_name} from "
                                                                                 f"the TTS list"))
        else:
            speaking_list.append(member.id)
            await ctx.send(embed=self.bot.create_completed_embed("Enabled TTS", f"Added {member.display_name} to the "
                                                                                f"TTS list."))
        self.data["speaking"] = speaking_list

    @commands.command(pass_context=True)
    @speak_changer_check()
    async def lang(self, ctx, new_lang: str):
        server_languages = self.data.get("server_languages", {})
        server_languages[ctx.guild.id] = new_lang
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
        temp_file = "chris_temp{}.mp3".format(self.index_num)
        server_languages = self.data.get("server_languages", {})
        lang = server_languages.get(message.guild.id, "en")
        spoken_words = gTTS(message.clean_content, lang=lang)
        spoken_words.save(temp_file)
        current_file = "{}{}.wav".format(message.guild.id, self.index_num)
        self.index_num += 1
        if self.index_num == 10:
            self.index_num = 0
        while not os.path.exists(temp_file):
            await asyncio.sleep(0.1)
        segment = pydub.AudioSegment.from_file(temp_file, bitrate=356000)
        segment = effects.speedup(segment, 1.25, 150, 25)
        segment.set_frame_rate(16000).export(current_file, format="wav")
        while voice_client.is_playing():
            await asyncio.sleep(0.1)
        try:
            voice_client.play(discord.FFmpegPCMAudio(current_file))
        except discord.errors.ClientException:
            pass
        while voice_client.is_playing():
            await asyncio.sleep(0.5)
        os.remove(temp_file)
        os.remove(current_file)

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
