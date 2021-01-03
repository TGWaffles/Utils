import discord
import asyncio
import pydub
import os

from pydub import effects
from gtts import gTTS
from discord.ext import commands
from main import UtilsBot
from src.checks.role_check import is_staff, is_high_staff
from src.checks.custom_check import speak_changer_check
from src.storage import messages
from src.helpers.storage_helper import DataHelper


class TTS(commands.Cog):
    def __init__(self, bot: UtilsBot):
        self.bot = bot
        self.data = DataHelper()
        self.lang = "en"
        self.index_num = 0

    @commands.command(pass_context=True)
    @is_staff()
    async def disconnect(self, ctx):
        voice_clients = [x for x in self.bot.voice_clients if x.guild.id == ctx.guild.id]
        if len(voice_clients) == 0:
            await ctx.send(messages.no_voice_clients)
            return
        try:
            await voice_clients[0].disconnect()
        except Exception as e:
            await ctx.send(embed=self.bot.create_error_embed("Error disconnecting from vc: {}".format(e)))

    @commands.command(pass_context=True, name="speak_perms",
                      description="Gives other people access to the !speak command.")
    @is_high_staff()
    async def speak_perms(self, ctx, member: discord.Member):
        changer_list = self.data.get("speak_changer", [])
        if member.id in changer_list:
            await ctx.send(self.bot.create_error_embed(messages.already_has_perms))
            return
        changer_list.append(member.id)
        self.data["speak_changer"] = changer_list
        await ctx.send(embed=self.bot.create_completed_embed("Perms Granted",
                                                             f"Given {member.display_name} permissions!"))

    @commands.command(pass_context=True, name="speak", description="Adds a user to the TTS list.")
    @speak_changer_check()
    async def speak(self, ctx, member: discord.Member):
        speaking_list = self.data.get("speaking", [])
        if member.id in speaking_list:
            await ctx.send(embed=self.bot.create_error_embed(messages.already_speaking))
            return
        speaking_list.append(member.id)
        self.data["speaking"] = speaking_list
        await ctx.send(embed=self.bot.create_completed_embed("Enabled TTS", f"Added {member.display_name} to the TTS list."))

    @commands.command(pass_context=True, name="no_speak", description="Removes a user from the TTS list.")
    @speak_changer_check()
    async def no_speak(self, ctx, member: discord.Member):
        speaking_list = self.data.get("speaking", [])
        if member.id not in speaking_list:
            await ctx.send(embed=self.bot.create_error_embed(messages.not_already_speaking))
            return
        speaking_list.remove(member.id)
        self.data["speaking"] = speaking_list
        await ctx.send(embed=self.bot.create_completed_embed("Disabled TTS",
                                                       f"Removed {member.display_name} from the TTS list."))

    @commands.command(pass_context=True)
    @speak_changer_check()
    async def lang(self, ctx, new_lang: str):
        self.lang = new_lang
        await ctx.send(embed=self.bot.create_completed_embed("Language changed!", f"Changed voice language to {new_lang}"))

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
        spoken_words = gTTS(message.clean_content, lang=self.lang)
        spoken_words.save(temp_file)
        current_file = "chris_speak{}.wav".format(self.index_num)
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
