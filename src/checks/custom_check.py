from src.helpers.storage_helper import DataHelper
from discord.ext import commands
from src.storage import config


def speak_changer_check():
    async def predicate(ctx):
        data = DataHelper()
        all_perms = data.get("speak_changer", {})
        guild_perms = all_perms.get(str(ctx.guild.id), [])
        return (ctx.author.guild_permissions.administrator or ctx.author.id in guild_perms
                or ctx.author.id == config.owner_id)

    return commands.check(predicate)
