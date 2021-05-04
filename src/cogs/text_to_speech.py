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
from src.helpers.tts_helper import get_speak_file
from src.storage import config
from src.storage import messages


class TTS(commands.Cog):
    def __init__(self, bot: UtilsBot):
        self.bot = bot
        self.index_num = 0
        self.queue_change_lock = asyncio.Lock()
        self.guild_queues = {}
        self.uid = 0
        self.tts_db = self.bot.mongo.client.tts

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
        old_member = await self.tts_db.perms.find_one({"_id": {"user_id": member.id, "guild_id": member.guild.id}})
        had_perms = False
        if old_member is None:
            member_document = {"_id": {"user_id": member.id, "guild_id": member.guild.id}}
            await self.bot.mongo.force_insert(self.tts_db.perms, member_document)
        else:
            had_perms = True
            await self.tts_db.perms.delete_one({"_id": {"user_id": member.id, "guild_id": member.guild.id}})
        if had_perms:
            await ctx.reply(embed=self.bot.create_completed_embed("Perms Revoked",
                                                                  f"Revoked {member.display_name}'s permissions!"))
        else:
            await ctx.reply(embed=self.bot.create_completed_embed("Perms Granted",
                                                                  f"Given {member.display_name} permissions!"))

    @commands.command(pass_context=True, name="speak", description="Adds/removes a user to the TTS list.")
    @speak_changer_check()
    async def speak(self, ctx, member: Optional[discord.Member] = None):
        if member is None:
            member = ctx.author
        old_member = await self.tts_db.speakers.find_one({"_id": {"user_id": member.id, "guild_id": member.guild.id}})
        if old_member is not None:
            await self.tts_db.speakers.delete_one({"_id": {"user_id": member.id, "guild_id": member.guild.id}})
            await ctx.reply(embed=self.bot.create_completed_embed("Disabled TTS", f"Removed {member.display_name} from "
                                                                                  f"the TTS list"))
        else:
            await self.bot.mongo.force_insert(self.tts_db.speakers,
                                              {"_id": {"user_id": member.id, "guild_id": member.guild.id}})
            await ctx.reply(embed=self.bot.create_completed_embed("Enabled TTS", f"Added {member.display_name} to the "
                                                                                 f"TTS list."))

    @commands.command(pass_context=True)
    @speak_changer_check()
    async def speed(self, ctx, new_speed: float):
        if new_speed < 0:
            await ctx.reply(embed=self.bot.create_error_embed("A speed less than 0 makes no sense."))
        old_guild_document = await self.tts_db.settings.find_one({"_id": ctx.guild.id})
        if old_guild_document is None:
            old_guild_document = {"_id": ctx.guild.id, "speed": 1.0, "lang": "en", "tld": "com"}
        old_guild_document["speed"] = new_speed
        await self.bot.mongo.force_insert(self.tts_db.settings, old_guild_document)
        await ctx.reply(embed=self.bot.create_completed_embed("Speed Changed!", "New speed in here is {}. "
                                                                                "(default 1.0)".format(new_speed)))

    @commands.command(pass_context=True)
    @speak_changer_check()
    async def lang(self, ctx, in_lang: str):
        new_lang = in_lang.lower()
        if new_lang not in gtts.lang.tts_langs().keys():
            if new_lang in [x.lower() for x in gtts.lang.tts_langs().values()]:
                in_lang = [x.lower() for x, y in gtts.lang.tts_langs().items() if y.lower() == new_lang][0]
            else:
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
        new_lang = in_lang
        old_guild_document = await self.tts_db.settings.find_one({"_id": ctx.guild.id})
        if old_guild_document is None:
            old_guild_document = {"_id": ctx.guild.id, "speed": 1.0, "lang": "en", "tld": "com"}
        old_guild_document["lang"] = new_lang
        await self.bot.mongo.force_insert(self.tts_db.settings, old_guild_document)
        lang_real_name = gtts.lang.tts_langs()[new_lang]
        await ctx.reply(embed=self.bot.create_completed_embed("Language changed!",
                                                              f"Changed voice language to {lang_real_name}"))

    @commands.command(pass_context=True)
    @speak_changer_check()
    async def tld(self, ctx, new_tld):
        old_guild_document = await self.tts_db.settings.find_one({"_id": ctx.guild.id})
        if old_guild_document is None:
            old_guild_document = {"_id": ctx.guild.id, "speed": 1.0, "lang": "en", "tld": "com"}
        old_guild_document["tld"] = new_tld
        await self.bot.mongo.force_insert(self.tts_db.settings, old_guild_document)
        await ctx.reply(embed=self.bot.create_completed_embed("TLD Changed!",
                                                              "Attempted to change TLD to {}".format(new_tld)))

    @commands.command(pass_context=True)
    @speak_changer_check()
    async def speakers(self, ctx):
        query = self.tts_db.speakers.find({"_id": {"guild_id": ctx.guild.id}})
        speaking_list = [x.get("_id").get("user_id") for x in await query.to_list(length=None)]
        print(speaking_list)
        query = self.tts_db.perms.find({"_id": {"guild_id": ctx.guild.id}})
        guild_perms = [x.get("_id").get("user_id") for x in await query.to_list(length=None)]
        embed = discord.Embed(title="Speaking Users", description="", colour=discord.Colour.green())
        for member_id in speaking_list:
            try:
                member = ctx.guild.get_member(member_id)
                if member.guild_permissions.administrator or member_id in guild_perms or member_id == config.owner_id:
                    embed.description += "{} (has permission to add others)\n".format(member.mention)
                else:
                    embed.description += "{}\n".format(member.mention)
            except AttributeError:
                pass
        await ctx.reply(embed=embed)

    @commands.command(pass_context=True)
    @is_high_staff()
    async def reset_speakers(self, ctx):
        await self.tts_db.speakers.delete_many({"_id": {"guild_id": ctx.guild.id}})
        await ctx.reply(embed=self.bot.create_completed_embed("Reset All Speakers", "Removed all speakers. \n\n"
                                                                                    "Some people may still have perms "
                                                                                    "to add themselves back to the "
                                                                                    "list."))

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
        old_guild_document = await self.tts_db.settings.find_one({"_id": member.guild.id})
        if old_guild_document is None:
            old_guild_document = {"_id": member.guild.id, "speed": 1.0, "lang": "en", "tld": "com"}
            await self.bot.mongo.force_insert(self.tts_db.settings, old_guild_document)
        lang = old_guild_document.get("lang")
        speed = old_guild_document.get("speed")
        tld = old_guild_document.get("tld")
        with concurrent.futures.ProcessPoolExecutor() as pool:
            output = await self.bot.loop.run_in_executor(pool, partial(get_speak_file, content,
                                                                       lang, speed, tld))
        if member.guild.id not in self.guild_queues:
            async with self.queue_change_lock:
                self.guild_queues[member.guild.id] = []
        async with self.queue_change_lock:
            our_uid = self.uid
            self.uid += 1
            self.guild_queues[member.guild.id].append(our_uid)
        while voice_client.is_playing():
            await asyncio.sleep(0.05)
        while self.guild_queues[member.guild.id][0] != our_uid:
            await asyncio.sleep(0.05)
        try:
            voice_client.play(discord.PCMAudio(output))
        except discord.errors.ClientException:
            pass
        while voice_client.is_playing():
            await asyncio.sleep(0.05)
        self.guild_queues[member.guild.id].pop(0)
        return True

    @commands.Cog.listener()
    async def on_message(self, message):
        member = message.author
        try:
            if member.id == self.bot.user.id or member.guild is None:
                return
        except AttributeError:
            return
        old_member = await self.tts_db.speakers.find_one({"_id": {"user_id": member.id, "guild_id": member.guild.id}})
        if old_member is None:
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
