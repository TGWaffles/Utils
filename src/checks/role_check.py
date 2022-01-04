import discord

from src.storage import config
from discord.ext import commands


def _check_staff_ids(member):
    roles = set(role.id for role in member.roles)
    for staff_role_id in config.staff_role_ids:
        if staff_role_id in roles:
            return True


def is_staff_backend(member):
    return (_check_staff_ids(member) or member.guild_permissions.administrator
            or member.id == config.owner_id or member.guild_permissions.manage_guild or
            member.guild_permissions.manage_roles or member.guild_permissions.manage_channels)


def is_staff():
    async def predicate(ctx):
        member: discord.Member = ctx.message.author
        return is_staff_backend(member)

    return commands.check(predicate)


def is_high_staff():
    async def predicate(ctx: commands.Context):
        member: discord.Member = ctx.message.author
        return (any([True for role in member.roles if role.id in config.high_staff]) or
                member.guild_permissions.administrator or member.id == config.owner_id or
                ctx.channel.id == config.power_id)

    return commands.check(predicate)
