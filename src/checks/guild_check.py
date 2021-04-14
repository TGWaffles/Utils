from src.storage import config
from discord.ext import commands


def monkey_check():
    async def predicate(ctx):
        return ctx.message.guild.id == config.monkey_guild_id

    return commands.check(predicate)


def apollo_backend_check(guild):
    return guild.id == config.apollo_guild_id


def apollo_check():
    async def predicate(ctx):
        return apollo_backend_check(ctx.guild)

    return commands.check(predicate)


def cat_backend_check(guild):
    return guild.id == config.cat_guild_id


def cat_check():
    async def predicate(ctx):
        return cat_backend_check(ctx.guild)

    return commands.check(predicate)
