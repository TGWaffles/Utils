from src.storage import config
from discord.ext import commands


def monkey_check():
    async def predicate(ctx):
        return ctx.message.guild.id == config.guild_id

    return commands.check(predicate)
