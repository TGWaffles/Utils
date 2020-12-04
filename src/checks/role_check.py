import discord

from src.storage import config
from discord.ext import commands


def is_staff():
    def predicate(ctx: commands.Context):
        member: discord.Member = ctx.message.author
        return config.staff_role_id in [role.id for role in member.roles] or member.guild_permissions.administrator

    commands.check(predicate)
