import asyncio

import discord
import youtube_dl
import aiohttp
import json.decoder
import re
import time
import random

from discord.ext import commands
from pytube import Playlist
from functools import partial

from main import UtilsBot
from src.helpers.storage_helper import DataHelper
from src.helpers.spotify_helper import SpotifySearcher

# TODO:
"""1. Add a true pagination system to the bot as a whole to allow !queue
2. Add !queue, !clearqueue, !dequeue <index>
3. Add !volume DONE
4. Add thumbnails (maybe) for "now playing" embeds.
5. Clean up help command for music related bot commands.
6. Add variable prefix (set to something obscure at first)
7. Add !pause DONE
8. <FUTURE> Start on web help page and change help handler to fully custom help handler."""

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
    def __init__(self, source, *, data, volume=0.5, resume_from=0):
        super().__init__(source, volume)
        self.data = data
        self.time = 0.0
        self.title = data.get('title')
        self.url = data.get('url')
        self.webpage_url = data.get("webpage_url")
        self.start_time = None
        self.resume_from = resume_from

    def read(self):
        if not self.start_time:
            self.start_time = time.time() - self.resume_from
        return super().read()

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
            attempts = 0
            while True:
                if attempts > 10:
                    return None
                attempts += 1
                future = loop.run_in_executor(None,
                                              lambda: youtube_dl.YoutubeDL(
                                                  ytdl_format_options).extract_info(url, download=False))
                try:
                    data = await asyncio.wait_for(future, 3)
                    if data is not None:
                        break
                except asyncio.TimeoutError:
                    pass
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
        self.spotify = SpotifySearcher(self.bot)

    def enqueue(self, guild, song_url, time=None, start=False):
        all_queues = self.data.get("song_queues", {})
        guild_queue: list = all_queues.get(str(guild.id), [])
        if time is None:
            to_queue = song_url
        else:
            to_queue = [song_url, time]
        if start:
            guild_queue.insert(0, to_queue)
        else:
            guild_queue.append(to_queue)
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
            try:
                json_response = await request.json()
            except json.decoder.JSONDecodeError:
                json_response = await YTDLSource.get_video_data(video_url, self.bot.loop)
        return json_response["title"]

    def thumbnail_from_url(self, video_url):
        exp = r"^.*((youtu.be\/)|(v\/)|(\/u\/\w\/)|(embed\/)|(watch\?))\??v?=?([^#&?]*).*"
        s = re.findall(exp, video_url)[0][-1]
        thumbnail = f"https://i.ytimg.com/vi/{s}/hqdefault.jpg"
        return thumbnail

    async def song_from_yt(self, song):
        attempts = 0
        while True:
            if attempts > 3:
                print(f"{song} failed after 3 attempts")
                return None
            attempts += 1
            youtube_song = await YTDLSource.get_video_data(song, self.bot.loop)
            if youtube_song is not None and youtube_song.get("webpage_url") is not None:
                return youtube_song.get("webpage_url")
            await asyncio.sleep(2)

    async def transform_spotify(self, to_play):
        string_playlist = await self.spotify.handle_spotify(to_play)
        if string_playlist is None:
            return None
        tasks = []
        for string_song in string_playlist:
            task = self.bot.loop.create_task(self.song_from_yt(string_song))
            task.set_name(string_song)
            tasks.append(task)
        link_playlist = await asyncio.gather(*tasks)
        link_playlist = [x for x in link_playlist if x is not None]
        if len(link_playlist) == 0:
            return None
        else:
            return link_playlist

    @commands.command()
    async def play(self, ctx, *, to_play):
        async with ctx.typing():
            if "spotify" in to_play:
                playlist_info = await self.transform_spotify(to_play)
                if playlist_info is None:
                    await ctx.reply(embed=self.bot.create_error_embed("I couldn't recognise that song, sorry!"))
            else:
                playlist_info = await self.bot.loop.run_in_executor(None, partial(self.get_playlist, to_play))
                if playlist_info is None:
                    video_info = await YTDLSource.get_video_data(to_play, self.bot.loop)
                    playlist_info = [video_info["webpage_url"]]
            first_song = playlist_info.pop(0)
            self.enqueue(ctx.guild, first_song)
            self.called_from[ctx.guild.id] = ctx.channel
            if not ctx.voice_client.is_playing():
                self.bot.loop.create_task(self.play_next_queued(ctx.voice_client))
            first_song_name = await self.title_from_url(first_song)
            embed = self.bot.create_completed_embed("Added song to queue!", f"Added [{first_song_name}]"
                                                                            f"({first_song}) "
                                                                            f"to queue!\n"
                                                                            f"Please note other songs in "
                                                                            f"a playlist may still be "
                                                                            f"processing.")
            embed.set_thumbnail(url=self.thumbnail_from_url(first_song))
            await ctx.reply(embed=embed)
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

    @commands.command()
    async def shuffle(self, ctx):
        all_queued = self.data.get("song_queues", {})
        guild_queued = all_queued.get(str(ctx.guild.id), [])
        if len(guild_queued) == 0:
            await ctx.reply(embed=self.bot.create_error_embed("There is no queue in your guild!"))
            return
        random.shuffle(guild_queued)
        all_queued[str(ctx.guild.id)] = guild_queued
        self.data["song_queues"] = all_queued
        await ctx.reply(embed=self.bot.create_completed_embed("Shuffled!", "Shuffled song queue! "
                                                                           "(skip to go to next shuffled song)"))

    async def play_next_queued(self, voice_client: discord.VoiceClient):
        if voice_client is None or not voice_client.is_connected():
            return
        while voice_client.is_playing():
            await asyncio.sleep(0.5)
        await asyncio.sleep(1)
        all_queued = self.data.get("song_queues", {})
        guild_queued = all_queued.get(str(voice_client.guild.id), [])
        if len(guild_queued) == 0:
            # await voice_client.disconnect()
            return
        next_song_url = guild_queued.pop(0)
        local_ffmpeg_options = ffmpeg_options.copy()
        resume_from = 0
        if type(next_song_url) == tuple or type(next_song_url) == list:
            next_song_url, resume_from = next_song_url
            local_ffmpeg_options['options'] = "-vn -ss {}".format(resume_from)
        all_queued[str(voice_client.guild.id)] = guild_queued
        self.data["song_queues"] = all_queued
        volume = self.data.get("song_volumes", {}).get(str(voice_client.guild.id), 0.5)
        data = await YTDLSource.get_video_data(next_song_url, self.bot.loop)
        source = YTDLSource(discord.FFmpegPCMAudio(data["url"], **local_ffmpeg_options),
                            data=data, volume=volume, resume_from=resume_from)
        voice_client.play(source, after=lambda e: self.bot.loop.create_task(self.play_next_queued(voice_client)))
        title = await self.title_from_url(next_song_url)
        embed = self.bot.create_completed_embed("Playing next song!", "Playing **[{}]({})**".format(title,
                                                                                                    next_song_url))
        embed.set_thumbnail(url=self.thumbnail_from_url(next_song_url))
        history = await self.called_from[voice_client.guild.id].history(limit=1).flatten()
        await self.called_from[voice_client.guild.id].send(embed=embed)

    @commands.command()
    async def resume(self, ctx):
        self.bot.loop.create_task(self.play_next_queued(ctx.voice_client))
        await ctx.reply(embed=self.bot.create_completed_embed("Resumed!", "Resumed playing."))

    @commands.command(aliases=["stop"])
    async def pause(self, ctx):
        currently_playing_url = ctx.voice_client.source.webpage_url
        current_time = int(time.time() - ctx.voice_client.source.start_time)
        self.enqueue(ctx.guild, currently_playing_url, int(current_time), start=True)
        ctx.voice_client.stop()
        await ctx.voice_client.disconnect()
        await ctx.reply(embed=self.bot.create_completed_embed("Successfully paused.", "Song paused successfully."))

    @commands.command()
    async def skip(self, ctx):
        ctx.voice_client.stop()
        await ctx.reply(embed=self.bot.create_completed_embed("Song skipped.", "Song skipped successfully."))

    @commands.command()
    async def volume(self, ctx, volume: float):
        if volume > 1:
            volume = volume / 100
        elif volume < 0:
            volume = 0
        all_guilds = self.data.get("song_volumes", {})
        all_guilds[str(ctx.guild.id)] = volume
        self.data["song_volumes"] = all_guilds
        ctx.voice_client.source.volume = volume
        await ctx.reply(embed=self.bot.create_completed_embed("Changed volume!", f"Set volume to "
                                                                                 f"{volume * 100}% for this guild!"))

    # async def queue(self, ctx):
    #     self.bot.add_listener()
    #     guild_queue = self.data.get("song_queues", {}).get(str(ctx.guild.id), [])
    #     queue_message = ""
    #     for index in range(len(guild_queue)):
    #         link = guild_queue[index]
    #         if index % 5 == 0:

    @volume.before_invoke
    @pause.before_invoke
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
