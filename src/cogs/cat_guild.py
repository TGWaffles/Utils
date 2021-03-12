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
        print("starting spotify...")
        if after.id == config.darby_id and after.guild.id == config.cat_guild_id:
            darby = after
        else:
            return
        music_channel = self.bot.get_channel(config.darby_channel_id)
        print("got channel")
        print(darby)
        print(darby.activities)
        if darby.activities:
            print("she has activities!")
            for activity in darby.activities:
                print(type(activity))
                if isinstance(activity, discord.Spotify):
                    print("spotify one!")
                    if activity.title != self.last_title:
                        print("not the same as last time.")
                        embed = discord.Embed(
                            title=f"{darby.name}'s Spotify",
                            description="Listening to {}".format(activity.title),
                            color=0xC902FF)
                        self.last_title = activity.title
                        print("set stuff up")
                        embed.set_thumbnail(url=activity.album_cover_url)
                        embed.add_field(name="Artist", value=activity.artist)
                        embed.add_field(name="Album", value=activity.album)
                        embed.set_footer(text="Song started at {}".format(activity.created_at.strftime("%H:%M")))
                        print("sending...")
                        await music_channel.send(embed=embed)
                        print("Sent!")


def setup(bot):
    cog = Cat(bot)
    bot.add_cog(cog)