from src.helpers.mongo_helper import MongoDB
from discord.ext import commands
from src.storage import config


def speak_changer_check():
    async def predicate(ctx):
        if ctx.author.guild_permissions.administrator:
            return True
        db = MongoDB()
        old_member = await db.client.tts.perms.find_one({"_id": {"user_id": ctx.author.id, "guild_id": ctx.guild.id}})
        return old_member is not None
    return commands.check(predicate)


def restart_check():
    async def predicate(ctx):
        db = MongoDB()
        query = db.client.discord.restart.find()
        restart_users = [x.get("_id") for x in await query.to_list(length=None)]
        return ctx.author.id in restart_users or ctx.author.id == config.owner_id

    return commands.check(predicate)
