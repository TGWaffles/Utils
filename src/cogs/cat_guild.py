import asyncio

import discord
from discord.ext import commands, tasks

from main import UtilsBot
from src.storage import config


class Cat(commands.Cog):
    def __init__(self, bot: UtilsBot):
        self.bot: UtilsBot = bot
        self.last_title = ""

    @commands.Cog.listener()
    async def on_member_update(self, before, after):
        if after.guild.id == config.cat_guild_id:
            member = after
        else:
            return
        music_channel = self.bot.get_channel(config.darby_channel_id)
        if member.activities:
            for activity in member.activities:
                if isinstance(activity, discord.Spotify):
                    if activity.title != self.last_title:
                        embed = discord.Embed(
                            title=f"{member.name}'s Spotify",
                            description="Listening to {}".format(activity.title),
                            color=discord.Colour.green())
                        self.last_title = activity.title
                        embed.set_thumbnail(url=activity.album_cover_url)
                        embed.add_field(name="Artist", value=activity.artist)
                        embed.add_field(name="Album", value=activity.album)
                        embed.set_footer(text="Song started at {}".format(activity.created_at.strftime("%H:%M")))
                        await music_channel.send(embed=embed)


def setup(bot):
    cog = Cat(bot)
    bot.add_cog(cog)
