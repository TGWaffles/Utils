from src.storage import config
from discord.ext import commands


def is_owner():
    async def predicate(ctx):
        return ctx.message.author.id == config.owner_id
    return commands.check(predicate)
