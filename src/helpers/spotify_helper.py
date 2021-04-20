import asyncio

import requests
import spotipy
from spotipy.oauth2 import SpotifyClientCredentials
from functools import partial

from main import UtilsBot
from src.storage.token import *


class SpotifySearcher:
    def __init__(self, bot: UtilsBot):
        self.spotify = None
        self.bot = bot
        self.ready = False
        bot.loop.run_in_executor(None, self.authenticate)

    def authenticate(self):
        credentials = SpotifyClientCredentials(client_id=spotify_id,
                                               client_secret=spotify_secret)
        self.spotify = spotipy.Spotify(client_credentials_manager=credentials)
        self.ready = True

    def get_playlist(self, playlist):
        try:
            response = self.spotify.playlist_items(playlist)
        except (requests.exceptions.HTTPError, spotipy.SpotifyException):
            return None
        items_response = response["items"]
        playlist_as_names = []
        for item in items_response:
            name = item.get("track").get("name")
            first_artist = item.get("track").get("artists")[0].get("name")
            url = item.get("track").get("external_urls").get("spotify")
            album = item.get("track").get("album", {}).get("name", "")
            if album != "":
                album = "from " + album
            playlist_as_names.append((url, f"{name} by {first_artist} {album}"))
        return playlist_as_names

    def get_track(self, track):
        try:
            response = self.spotify.track(track)
        except (requests.exceptions.HTTPError, spotipy.SpotifyException):
            return None
        name = response.get("name")
        first_artist = response.get("artists")[0].get("name")
        album = response.get("album", {}).get("name", "")
        if album != "":
            album = "from " + album
        return response.get('external_urls').get('spotify'), f"{name} by {first_artist} {album}"

    async def handle_spotify(self, media_identifier):
        while not self.ready:
            await asyncio.sleep(1)
        playlist = await self.bot.loop.run_in_executor(None, partial(self.get_playlist, media_identifier))
        if playlist is None:
            track = await self.bot.loop.run_in_executor(None, partial(self.get_track, media_identifier))
            if track is None:
                return None
            return [track]
        return playlist
