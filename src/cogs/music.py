import asyncio

import discord
import youtube_dl
import aiohttp

from discord.ext import commands
from pytube import Playlist
from functools import partial

from main import UtilsBot
from src.helpers.storage_helper import DataHelper

youtube_dl.utils.bug_reports_message = lambda: ''

ytdl_format_options = {
    'format': 'bestaudio/best',
    'outtmpl': '%(extractor)s-%(id)s-%(title)s.%(ext)s',
    'restrictfilenames': True,
    'noplaylist': True,
    'nocheckcertificate': True,
    'ignoreerrors': False,
    'logtostderr': False,
    'quiet': True,
    'no_warnings': True,
    'default_search': 'auto',
    'source_address': '0.0.0.0'  # bind to ipv4 since ipv6 addresses cause issues sometimes
}

ffmpeg_options = {
    'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5',
    'options': '-vn'
}

ytdl = youtube_dl.YoutubeDL(ytdl_format_options)


class YTDLSource(discord.PCMVolumeTransformer):
    def __init__(self, source, *, data, volume=0.5):
        super().__init__(source, volume)

        self.data = data

        self.title = data.get('title')
        self.url = data.get('url')

    @classmethod
    async def from_url(cls, url, *, loop=None, stream=False):
        data = await cls.get_video_data(url, loop)
        if data is None:
            return None
        return cls(discord.FFmpegPCMAudio(data["url"], **ffmpeg_options), data=data)

    @staticmethod
    async def get_video_data(url, loop=None):
        loop = loop or asyncio.get_event_loop()
        try:
            data = await loop.run_in_executor(None, lambda: ytdl.extract_info(url, download=False))
        except youtube_dl.utils.DownloadError:
            return None
        if 'entries' in data and len(data['entries']) > 0:
            # take first item from a playlist
            data = data['entries'][0]
        if data.get('url', None) is None:
            return None
        return data


class Music(commands.Cog):
    def __init__(self, bot: UtilsBot):
        self.bot = bot
        self.data = DataHelper()
        self.data["song_queues"] = {}
        self.called_from = {}

    def enqueue(self, guild, song_data):
        all_queues = self.data.get("song_queues", {})
        guild_queue = all_queues.get(str(guild.id), [])
        guild_queue.append(song_data)
        all_queues[str(guild.id)] = guild_queue
        self.data["song_queues"] = all_queues
        return True

    @staticmethod
    def get_playlist(provided_info):
        try:
            playlist_info = Playlist(provided_info).video_urls
        except KeyError:
            playlist_info = None
        return playlist_info

    async def title_from_url(self, video_url):
        params = {"format": "json", "url": video_url}
        url = "https://www.youtube.com/oembed"
        async with aiohttp.ClientSession() as session:
            request = await session.get(url=url, params=params)
            json_response = await request.json()
        return json_response["title"]

    @commands.command()
    async def play(self, ctx, *, to_play):
        async with ctx.typing():
            playlist_info = await self.bot.loop.run_in_executor(None, partial(self.get_playlist, to_play))
            if playlist_info is None:
                playlist_info = await YTDLSource.get_video_data(to_play, self.bot.loop)
                playlist_info = [playlist_info["webpage_url"]]
            first_song = playlist_info.pop(0)
            self.enqueue(ctx.guild, first_song)
            self.called_from[ctx.guild.id] = ctx.channel
            if not ctx.voice_client.is_playing():
                self.bot.loop.create_task(self.play_next_queued(ctx.voice_client))
            first_song_name = await self.title_from_url(first_song)
            await ctx.reply(embed=self.bot.create_completed_embed("Added song to queue!", f"Added {first_song_name} "
                                                                                          f"to queue!\n"
                                                                                          f"Please note other songs in a playlist may still be "
                                                                                          f"processing."))
            futures = []
            for url in playlist_info:
                futures.append(self.bot.loop.create_task(self.title_from_url(url), name=url))
            await asyncio.sleep(2)
            titles = await asyncio.gather(*futures)
            successfully_added = ""
            for index, title in enumerate(titles):
                self.enqueue(ctx.guild, playlist_info[index])
                successfully_added += f"{index + 1}. **{title}**\n"
        if successfully_added != "":
            for short_text in self.bot.split_text(successfully_added):
                await ctx.reply(embed=self.bot.create_completed_embed("Successfully queued songs!", short_text))

    async def play_next_queued(self, voice_client: discord.VoiceClient):
        if voice_client is None or not voice_client.is_connected():
            return
        while voice_client.is_playing():
            await asyncio.sleep(0.5)
        await asyncio.sleep(1)
        all_queued = self.data.get("song_queues", {})
        guild_queued = all_queued.get(str(voice_client.guild.id), [])
        if len(guild_queued) == 0:
            await voice_client.disconnect()
            return
        next_song_url = guild_queued.pop(0)
        all_queued[str(voice_client.guild.id)] = guild_queued
        self.data["song_queues"] = all_queued
        volume = self.data.get("song_volumes", {}).get(str(voice_client.guild.id), 0.5)
        data = await YTDLSource.get_video_data(next_song_url, self.bot.loop)
        source = YTDLSource(discord.FFmpegPCMAudio(data["url"], **ffmpeg_options),
                            data=data, volume=volume)
        voice_client.play(source, after=lambda e: self.bot.loop.create_task(self.play_next_queued(voice_client)))
        title = await self.title_from_url(next_song_url)
        await self.called_from[voice_client.guild.id].send(embed=self.bot.create_completed_embed("Playing next song!",
                                                           "Playing **{}**".format(title)))

    @commands.command()
    async def resume(self, ctx):
        self.bot.loop.create_task(self.play_next_queued(ctx.voice_client))

    @commands.command()
    async def skip(self, ctx):
        ctx.voice_client.stop()
        await ctx.reply(embed=self.bot.create_completed_embed("Song skipped.", "Song skipped successfully."))

    @play.before_invoke
    @resume.before_invoke
    @skip.before_invoke
    async def ensure_voice(self, ctx):
        if ctx.voice_client is None:
            if ctx.author.voice:
                await ctx.author.voice.channel.connect()
            else:
                await ctx.reply(embed=self.bot.create_error_embed("You are not connected to a voice channel."))
                raise commands.CommandError("Author not connected to a voice channel.")
        elif not ctx.author.voice or ctx.voice_client.channel != ctx.author.voice.channel:
            await ctx.reply(embed=self.bot.create_error_embed("You have to be connected to the voice channel to "
                                                              "execute these commands!"))
            raise commands.CommandError("Author not connected to the correct voice channel.")


def setup(bot: UtilsBot):
    cog = Music(bot)
    bot.add_cog(cog)
