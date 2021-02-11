from src.storage import config
from discord.ext import commands


def monkey_check():
    async def predicate(ctx):
        return ctx.message.guild.id == config.monkey_guild_id

    return commands.check(predicate)


def sparky_check():
    async def predicate(ctx):
        return ctx.message.guild.id == config.sparky_guild_id

    return commands.check(predicate)
