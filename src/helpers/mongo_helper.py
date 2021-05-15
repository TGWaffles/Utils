import asyncio
import datetime

import discord
import motor.motor_asyncio
from pymongo.errors import BulkWriteError

from src.storage import config


class MongoDB:
    def __init__(self):
        self.client = motor.motor_asyncio.AsyncIOMotorClient(config.mongo_connection_uri)
        self.discord_db = self.client.discord

    @staticmethod
    async def force_insert(collection, document):
        if "_id" in document:
            await collection.update_one({"_id": document.get("_id")}, {"$set": document}, upsert=True)
        else:
            await collection.insert_one(document)

    @staticmethod
    async def find_by_id(collection, search_id):
        result = await collection.find_one({"_id": search_id})
        if result is None:
            return {}
        return result

    async def insert_guild(self, guild: discord.Guild):
        guild_document = {"_id": guild.id, "name": guild.name, "removed": False}
        await self.force_insert(self.discord_db.guilds, guild_document)
        return guild_document

    async def insert_channel(self, channel: discord.TextChannel):
        guild_result = await self.discord_db.guilds.find_one({"_id": channel.guild.id})
        if guild_result is None:
            await self.insert_guild(channel.guild)
        channel_document = {"_id": channel.id, "name": channel.name, "guild_id": channel.guild.id, "deleted": False,
                            "excluded": False}
        await self.force_insert(self.discord_db.channels, channel_document)

    async def insert_user(self, user: discord.User):
        user_document = {"_id": user.id, "name": user.name, "bot": user.bot}
        await self.force_insert(self.discord_db.users, user_document)

    async def insert_member(self, member: discord.Member):
        if isinstance(member, discord.User):
            return
        user_result = await self.discord_db.users.find_one({"_id": member.id})
        if user_result is None:
            # noinspection PyTypeChecker
            await self.insert_user(member)
        guild_result = await self.discord_db.guilds.find_one({"_id": member.guild.id})
        if guild_result is None:
            await self.insert_guild(member.guild)
        member_document = {"_id": {"user_id": member.id, "guild_id": member.guild.id},
                           "nick": member.nick, "joined_at": member.joined_at, "deleted": False}
        await self.force_insert(self.discord_db.members, member_document)

    async def insert_message(self, message: discord.Message):
        channel_result = await self.discord_db.channels.find_one({"_id": message.channel.id})
        if channel_result is None:
            await self.insert_channel(message.channel)
        else:
            if channel_result.get("nostore", False):
                return
        member_result = await self.discord_db.members.find_one({"_id": message.author.id})
        if member_result is None:
            await self.insert_member(message.author)
        message_document = {"_id": message.id, "channel_id": message.channel.id, "user_id": message.author.id,
                            "content": message.content, "created_at": message.created_at, "guild_id": message.guild.id,
                            "embeds": [embed.to_dict() for embed in message.embeds if embed is not None],
                            "deleted": False, "edits": []}
        await self.force_insert(self.discord_db.messages, message_document)

    async def insert_channel_messages(self, list_of_messages):
        """Requires that all messages be from the same channel"""
        if len(list_of_messages) == 0:
            return
        all_users = set()
        all_channels = set()
        message_documents = []
        for message in list_of_messages:
            all_users.add(message.author)
            all_channels.add(message.channel)
            message_documents.append({"_id": message.id, "channel_id": message.channel.id, "user_id": message.author.id,
                                      "content": message.content, "created_at": message.created_at,
                                      "guild_id": message.guild.id,
                                      "embeds": [embed.to_dict() for embed in message.embeds if embed is not None],
                                      "deleted": False, "edits": []})
        user_documents = []
        channel_documents = []
        for user in all_users:
            user_documents.append({"_id": user.id, "name": user.name, "bot": user.bot})
        try:
            await self.discord_db.users.insert_many(user_documents, ordered=False)
        except BulkWriteError:
            pass
        for channel in all_channels:
            channel_documents.append({"_id": channel.id, "name": channel.name, "guild_id": channel.guild.id,
                                      "deleted": False, "excluded": False})
        try:
            await self.discord_db.channels.insert_many(channel_documents, ordered=False)
        except BulkWriteError:
            pass
        try:
            await self.discord_db.messages.insert_many(message_documents, ordered=False)
        except BulkWriteError:
            pass

    async def message_edit(self, payload: discord.RawMessageUpdateEvent):
        is_bot = payload.data.get("author", {}).get("bot", False)
        last_edited = payload.data.get('edited_timestamp')
        if last_edited is None:
            return None
        timestamp = datetime.datetime.fromisoformat(last_edited)
        message_document = await self.discord_db.messages.find_one({"_id": payload.message_id})
        if message_document is None:
            return
        old_edits = sorted(message_document.get("edits", []), key=lambda x: x.get("timestamp"))
        if len(old_edits) > 10 and is_bot:
            return
        edit_document = {"timestamp": timestamp, "content": payload.data.get("content", None),
                         "embeds": payload.data.get("embeds", [])}
        if len(old_edits) > 0 and old_edits[-1].get("timestamp").replace(tzinfo=datetime.timezone.utc) \
                > timestamp - datetime.timedelta(seconds=0.5):
            old_edits[-1] = edit_document
        else:
            old_edits.append(edit_document)
        await self.discord_db.messages.update_one({"_id": payload.message_id}, {'$set': {"edits": old_edits}})

    @staticmethod
    async def find_by_column(collection, column, value):
        result = await collection.find_one({column: value})
        return result

    @staticmethod
    async def fetch_all(collection):
        query = collection.find()
        results = await query.to_list(length=None)
        return results


async def main():
    # bot = commands.Bot(command_prefix="NoPrefix", intents=discord.Intents.all())
    # await bot.login(token)
    # asyncio.get_event_loop().create_task(bot.connect())
    # await bot.wait_until_ready()
    # for guild in bot.guilds:
    #     print(guild.name)
    # database = DatabaseHelper()
    # session = database.session_creator()
    db = MongoDB()
    client = db.client
    discord_db = client.discord
    print()


if __name__ == '__main__':
    loop = asyncio.get_event_loop()
    loop.create_task(main())
    loop.run_forever()
