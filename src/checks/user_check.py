from src.storage import config
from discord.ext import commands


def is_owner():
    async def predicate(ctx):
        return ctx.message.author.id == config.owner_id

    return commands.check(predicate)

def is_kick_rouletter():
    async def predicate(ctx):
        return ctx.message.author.id in [489101454930345999, 230778630597246983, 305797476290527235, 554777326379073546]

    return commands.check(predicate)
