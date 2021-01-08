import discord
import datetime

from src.storage import config, messages
from discord.ext import commands
from main import UtilsBot
from src.checks.role_check import is_staff
from src.checks.user_check import is_owner
from src.checks.guild_check import monkey_check


class Monkey(commands.Cog):
    def __init__(self, bot: UtilsBot):
        self.bot: UtilsBot = bot
        self.july = datetime.datetime(2020, 7, 1, tzinfo=datetime.timezone.utc)

    def is_og(self, member: discord.Member):
        first_join_date = member.joined_at
        # noinspection SpellCheckingInspection
        first_join_date = first_join_date.replace(tzinfo=datetime.timezone.utc)
        return first_join_date < self.july

    @commands.command(pass_context=True)
    @is_owner()
    @monkey_check()
    async def check_og(self, ctx, member: discord.Member = None):
        if member is None:
            member = ctx.message.author
        is_og = self.is_og(member)
        embed = discord.Embed(title="OG Check")
        embed.set_author(name=member.name, icon_url=member.avatar_url)
        embed.description = "{} Member {} OG".format(("❌", "✅")[int(is_og)], ("is not", "is")[int(is_og)])
        embed.colour = (discord.Colour.red(), discord.Colour.green())[int(is_og)]
        embed.timestamp = member.joined_at
        await ctx.send(embed=embed)


def setup(bot):
    cog = Monkey(bot)
    bot.add_cog(cog)
