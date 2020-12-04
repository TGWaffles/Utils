import discord

from src.storage import config
from discord.ext import commands


def is_staff():
    async def predicate(ctx: commands.Context):
        member: discord.Member = ctx.message.author
        return config.staff_role_id in [role.id for role in member.roles] or member.guild_permissions.administrator

    return commands.check(predicate)


def is_high_staff():
    async def predicate(ctx: commands.Context):
        member: discord.Member = ctx.message.author
        return (any([True for role in member.roles if role.id in config.high_staff]) or
                member.guild_permissions.administrator)

    return commands.check(predicate)
