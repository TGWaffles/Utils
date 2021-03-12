import asyncio

import discord
from discord.ext import commands, tasks

from main import UtilsBot
from src.storage import config


class Cat(commands.Cog):
    def __init__(self, bot: UtilsBot):
        self.bot: UtilsBot = bot
        self.last_title = ""
        self.update_spotify_embed.start()

    @tasks.loop(seconds=5, count=None)
    async def update_spotify_embed(self):
        cat_guild = self.bot.get_guild(config.cat_guild_id)
        darby: discord.Member = await cat_guild.fetch_member(config.darby_id)
        music_channel = self.bot.get_channel(config.darby_channel_id)
        if darby.activities:
            for activity in darby.activities:
                if isinstance(activity, discord.Spotify):
                    if activity.title != self.last_title:
                        embed = discord.Embed(
                            title=f"{darby.name}'s Spotify",
                            description="Listening to {}".format(activity.title),
                            color=0xC902FF)
                        self.last_title = activity.title
                        embed.set_thumbnail(url=activity.album_cover_url)
                        embed.add_field(name="Artist", value=activity.artist)
                        embed.add_field(name="Album", value=activity.album)
                        embed.set_footer(text="Song started at {}".format(activity.created_at.strftime("%H:%M")))
                        await music_channel.send(embed=embed)


def setup(bot):
    cog = Cat(bot)
    bot.add_cog(cog)
