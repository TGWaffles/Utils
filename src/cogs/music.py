import asyncio

import discord
import youtube_dl
import aiohttp
import json.decoder
import re
import time
import random
import youtubesearchpython.__future__ as youtube_search

from discord.ext import commands
from pytube import Playlist
from functools import partial

from main import UtilsBot
from src.helpers.storage_helper import DataHelper
from src.helpers.spotify_helper import SpotifySearcher
from src.helpers.paginator import Paginator
from src.checks.role_check import is_staff

# TODO:
"""1. Add a true pagination system to the bot as a whole to allow !queue DONE
2. Add !queue DONE, !clearqueue, !dequeue <index>
3. Add !volume DONE
4. Add thumbnails (maybe) for "now playing" embeds. DONE
5. Clean up help command for music related bot commands.
6. Add variable prefix (set to something obscure at first) DONE
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
    async def get_video_data(url, loop=None, search=False):
        loop = loop or asyncio.get_event_loop()
        if search:
            query = youtube_search.CustomSearch(url, youtube_search.VideoSortOrder.relevance, limit=1)
            data = await query.next()
            return json.loads(data.get("result")[0]).get("link")
        else:
            try:
                attempts = 0
                while True:
                    if attempts > 10:
                        return None
                    attempts += 1
                    ydl = youtube_dl.YoutubeDL(ytdl_format_options)
                    ydl._ies = [ydl.get_info_extractor('Youtube')]
                    future = loop.run_in_executor(None, lambda: ydl.extract_info(url, download=False))
                    try:
                        data = await asyncio.wait_for(future, 10)
                        if data is not None:
                            break
                    except asyncio.TimeoutError:
                        pass
            except youtube_dl.utils.DownloadError:
                return None
            if 'entries' in data and len(data['entries']) > 0:
                print(url)
                print([(x["title"], x["view_count"]) for x in sorted(data['entries'], key=lambda x: x.get("view_count", 0), reverse=True)])
                data = sorted(data['entries'], key=lambda x: x.get("view_count", 0), reverse=True)[0]
                # take first item from a playlist
                # data = data['entries'][0]
        if data.get('url', None) is None:
            return None
        return data


class Music(commands.Cog):
    def __init__(self, bot: UtilsBot):
        self.bot = bot
        self.data = DataHelper()
        # self.data["song_queues"] = {}
        if self.data.get("called_from", None) is None:
            self.data["called_from"] = {}
        self.spotify = SpotifySearcher(self.bot)
        self.url_to_title_cache = {}
        self.bot.loop.create_task(self.restart_watcher())

    async def restart_watcher(self):
        self.bot.restart_event = asyncio.Event()
        while True:
            try:
                await self.bot.wait_until_ready()
                await self.post_restart_resume()
                await self.bot.restart_event.wait()
                async with self.bot.restart_waiter_lock:
                    self.bot.restart_waiters += 1
                for voice_client in self.bot.voice_clients:
                    if not isinstance(voice_client, discord.VoiceClient):
                        continue
                    if not isinstance(voice_client.source, YTDLSource):
                        continue
                    await self.pause_voice_client(voice_client)
                    resume_from = self.data.get("resume_voice", [])
                    resume_from.append(voice_client.channel.id)
                    self.data["resume_voice"] = resume_from
                async with self.bot.restart_waiter_lock:
                    self.bot.restart_waiters -= 1
                return
            except RuntimeError:
                pass

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
        if video_url in self.url_to_title_cache:
            return self.url_to_title_cache[video_url]
        if "open.spotify.com" in video_url:
            _, title = await self.bot.loop.run_in_executor(None, partial(self.spotify.get_track, video_url))
            self.url_to_title_cache[video_url] = title
            return title
        params = {"format": "json", "url": video_url}
        url = "https://www.youtube.com/oembed"
        async with aiohttp.ClientSession() as session:
            request = await session.get(url=url, params=params)
            try:
                json_response = await request.json()
            except json.decoder.JSONDecodeError:
                json_response = await YTDLSource.get_video_data(video_url, self.bot.loop)
        title = json_response["title"]
        self.url_to_title_cache[video_url] = title
        return title

    @staticmethod
    def thumbnail_from_url(video_url):
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
            youtube_song = await YTDLSource.get_video_data(song, self.bot.loop, search=True)
            if youtube_song is not None and youtube_song.get("webpage_url") is not None:
                return youtube_song.get("webpage_url")
            await asyncio.sleep(2)

    async def transform_spotify(self, to_play):
        spotify_playlist = await self.spotify.handle_spotify(to_play)
        if spotify_playlist is None:
            return None
        for song in spotify_playlist:
            self.url_to_title_cache[song[0]] = song[1]
        return [song[0] for song in spotify_playlist]

    async def transform_single_song(self, song):
        if "open.spotify.com" not in song:
            return song
        _, string_song = await self.bot.loop.run_in_executor(None, partial(self.spotify.get_track, song))
        if string_song is None:
            return None
        youtube_link = await self.song_from_yt(string_song)
        return youtube_link

    async def send_queue(self, channel, reply_message=None):
        all_queued = self.data.get("song_queues", {})
        guild_queued = all_queued.get(str(channel.guild.id), [])
        if len(guild_queued) == 0:
            return False
        futures = []
        titles = []
        for url in guild_queued:
            if type(url) == tuple or type(url) == list:
                url, _ = url
            if url in self.url_to_title_cache:
                titles.append(self.url_to_title_cache[url])
                continue
            titles.append(None)
            futures.append(self.bot.loop.create_task(self.title_from_url(url), name=url))
        waited_titles = await asyncio.gather(*futures)
        for index, title in enumerate(titles.copy()):
            if title is None:
                # noinspection PyUnresolvedReferences
                titles[index] = waited_titles.pop(0)
        successfully_added = ""
        for index, title in enumerate(titles):
            successfully_added += f"{index + 1}. **{title}**\n"
        paginator = Paginator(self.bot, channel, "Queued Songs", successfully_added, 500, reply_message=reply_message)
        await paginator.start()
        return True

    @commands.command()
    async def queue(self, ctx):
        if not await self.send_queue(ctx.channel, ctx):
            await ctx.reply(embed=self.bot.create_error_embed("No songs queued!"))
            return

    @commands.command(aliases=["clearqueue"])
    @is_staff()
    async def clear_queue(self, ctx):
        all_queued = self.data.get("song_queues", {})
        guild_queued = all_queued.get(str(ctx.guild.id), [])
        if len(guild_queued) == 0:
            await ctx.reply(embed=self.bot.create_error_embed("There are no songs queued."))
            return
        all_queued[str(ctx.guild.id)] = []
        self.data["song_queues"] = all_queued
        await ctx.reply(embed=self.bot.create_completed_embed("Cleared Queue!", "Queue cleared!"))

    @commands.command(aliases=["unqueue"])
    async def dequeue(self, ctx, index: int):
        all_queued = self.data.get("song_queues", {})
        guild_queued = all_queued.get(str(ctx.guild.id), [])
        if not 0 < index < len(guild_queued) + 1:
            await ctx.reply(embed=self.bot.create_error_embed("That is not a valid queue position!"))
            return
        index -= 1
        song = guild_queued.pop(index)
        all_queued[str(ctx.guild.id)] = guild_queued
        self.data["song_queues"] = all_queued
        title = await self.title_from_url(song)
        await ctx.reply(embed=self.bot.create_completed_embed("Successfully removed song from queue!",
                                                              f"Successfully removed [{title}]({song})"
                                                              f" from the queue!"))

    @dequeue.error
    async def dequeue_error(self, ctx, error):
        if isinstance(error, commands.ConversionError):
            await ctx.reply(embed=self.bot.create_error_embed("Please refer to the song by index, not name, "
                                                              "so I don't guess wrong! \n"
                                                              "(do !queue to see the queue with indexes)"))

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
            first_song = await self.transform_single_song(first_song)
            self.enqueue(ctx.guild, first_song)
            callers = self.data.get("called_from", {})
            callers[str(ctx.guild.id)] = ctx.channel.id
            self.data["called_from"] = callers
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
            await self.send_queue(ctx.channel, ctx)

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
        await asyncio.sleep(0.5)
        all_queued = self.data.get("song_queues", {})
        guild_queued = all_queued.get(str(voice_client.guild.id), [])
        if len(guild_queued) == 0:
            # await voice_client.disconnect()
            return
        next_song_url = guild_queued.pop(0)
        all_queued[str(voice_client.guild.id)] = guild_queued
        self.data["song_queues"] = all_queued
        local_ffmpeg_options = ffmpeg_options.copy()
        resume_from = 0
        if type(next_song_url) == tuple or type(next_song_url) == list:
            next_song_url, resume_from = next_song_url
            local_ffmpeg_options['options'] = "-vn -ss {}".format(resume_from)
        volume = self.data.get("song_volumes", {}).get(str(voice_client.guild.id), 0.5)
        if next_song_url is None:
            self.bot.loop.create_task(self.play_next_queued(voice_client))
            return
        next_song_url = await self.transform_single_song(next_song_url)
        if next_song_url is None:
            self.bot.loop.create_task(self.play_next_queued(voice_client))
            return
        data = await YTDLSource.get_video_data(next_song_url, self.bot.loop)
        source = YTDLSource(discord.FFmpegPCMAudio(data["url"], **local_ffmpeg_options),
                            data=data, volume=volume, resume_from=resume_from)
        while voice_client.is_playing():
            await asyncio.sleep(0.5)
        voice_client.play(source, after=lambda e: self.bot.loop.create_task(self.play_next_queued(voice_client)))
        title = await self.title_from_url(next_song_url)
        embed = self.bot.create_completed_embed("Playing next song!", "Playing **[{}]({})**".format(title,
                                                                                                    next_song_url))
        embed.set_thumbnail(url=self.thumbnail_from_url(next_song_url))
        called_channel = self.bot.get_channel(self.data["called_from"][str(voice_client.guild.id)])
        history = await called_channel.history(limit=1).flatten()
        if len(history) > 0 and history[0].author.id == self.bot.user.id:
            old_message = history[0]
            if len(old_message.embeds) > 0:
                if old_message.embeds[0].title == "Playing next song!":
                    await old_message.edit(embed=embed)
                    return
        await called_channel.send(embed=embed)

    @commands.command()
    async def resume(self, ctx):
        self.bot.loop.create_task(self.play_next_queued(ctx.voice_client))
        await ctx.reply(embed=self.bot.create_completed_embed("Resumed!", "Resumed playing."))

    async def post_restart_resume(self):
        for voice_channel_id in self.data.get("resume_voice", []):
            voice_channel = self.bot.get_channel(voice_channel_id)
            try:
                voice_client = await voice_channel.connect()
            except AttributeError:
                continue
            self.bot.loop.create_task(self.play_next_queued(voice_client))
        self.data["resume_voice"] = []

    async def pause_voice_client(self, voice_client):
        if voice_client.source is not None:
            currently_playing_url = voice_client.source.webpage_url
            current_time = int(time.time() - voice_client.source.start_time)
            self.enqueue(voice_client.guild, currently_playing_url, int(current_time), start=True)
        voice_client.stop()
        await voice_client.disconnect()

    @commands.command(aliases=["stop", "leave", "quit"])
    async def pause(self, ctx):
        await self.pause_voice_client(ctx.voice_client)
        await ctx.reply(embed=self.bot.create_completed_embed("Successfully paused.", "Song paused successfully."))

    async def skip_guild(self, guild):
        if guild.voice_client.is_playing():
            try:
                song = f" \"{guild.voice_client.source.title}\""
            except AttributeError:
                song = ""
            guild.voice_client.stop()
        else:
            all_queued = self.data.get("song_queues", {})
            guild_queued = all_queued.get(str(guild.id), [])
            if len(guild_queued) == 0:
                return None
            song_url = guild_queued.pop(0)
            all_queued[str(guild.id)] = guild_queued
            self.data["song_queues"] = all_queued
            song = f" \"{self.title_from_url(song_url)}\""
        return song

    @commands.command()
    async def skip(self, ctx):
        song = await self.skip_guild(ctx.guild)
        if song is None:
            await ctx.reply(embed=self.bot.create_error_embed("There is no song playing or queued!"))
            return
        await ctx.reply(embed=self.bot.create_completed_embed("Song skipped.", f"Song{song} skipped successfully."))

    @commands.command()
    async def volume(self, ctx, volume: float):
        volume = volume / 100
        if volume < 0:
            volume = 0
        all_guilds = self.data.get("song_volumes", {})
        all_guilds[str(ctx.guild.id)] = volume
        self.data["song_volumes"] = all_guilds
        try:
            ctx.voice_client.source.volume = volume
        except AttributeError:
            pass
        await ctx.reply(embed=self.bot.create_completed_embed("Changed volume!", f"Set volume to "
                                                                                 f"{volume * 100}% for this guild!"))

    # async def queue(self, ctx):
    #     self.bot.add_listener()
    #     guild_queue = self.data.get("song_queues", {}).get(str(ctx.guild.id), [])
    #     queue_message = ""
    #     for index in range(len(guild_queue)):
    #         link = guild_queue[index]
    #         if index % 5 == 0:

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
