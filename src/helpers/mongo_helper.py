import asyncio
import datetime

import discord
import motor.motor_asyncio
from time import perf_counter, time
import ast
from discord.ext import commands

from src.helpers.sqlalchemy_helper import DatabaseHelper
from src.helpers.models.database_models import *
from src.storage.token import token


class MongoDB:
    def __init__(self):
        self.client = motor.motor_asyncio.AsyncIOMotorClient('mongodb://192.168.1.100:27017,'
                                                             '192.168.1.20:27017,'
                                                             '192.168.1.135:27017/?replicaSet=thomasRep0')
        self.discord_db = self.client.discord

    @staticmethod
    async def force_insert(collection, document):
        if "_id" in document:
            await collection.replace_one({"_id": document.get("_id")}, document, upsert=True)
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

    async def insert_channel(self, channel: discord.TextChannel):
        guild_result = await self.discord_db.guilds.find_one({"_id": channel.guild.id})
        if guild_result is None:
            await self.insert_guild(channel.guild)
        channel_document = {"_id": channel.id, "name": channel.name, "guild_id": channel.guild.id}
        await self.force_insert(self.discord_db.channels, channel_document)

    async def insert_user(self, user: discord.User):
        user_document = {"_id": user.id, "name": user.name, "bot": user.bot}
        await self.force_insert(self.discord_db.users, user_document)

    async def insert_member(self, member: discord.Member):
        user_result = await self.discord_db.users.find_one({"_id": member.id})
        if user_result is None:
            # noinspection PyTypeChecker
            await self.insert_user(member)
        guild_result = await self.discord_db.guilds.find_one({"_id": member.guild.id})
        if guild_result is None:
            await self.insert_guild(member.guild)
        member_document = {"_id": member.id, "nick": member.nick, "joined_at": member.joined_at,
                           "guild_id": member.guild.id}
        await self.force_insert(self.discord_db.members, member_document)

    async def insert_message(self, message: discord.Message):
        channel_result = await self.discord_db.channels.find_one({"_id": message.channel.id})
        if channel_result is None:
            await self.insert_channel(message.channel)
        member_result = await self.discord_db.members.find_one({"_id": message.author.id})
        if member_result is None:
            await self.insert_member(message.author)
        message_document = {"_id": message.id, "channel_id": message.channel.id, "user_id": message.author.id,
                            "content": message.content, "created_at": message.created_at, "guild_id": message.guild.id,
                            "embeds": [embed.to_dict() for embed in message.embeds], "deleted": False, "edits": []}
        await self.force_insert(self.discord_db.messages, message_document)

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
    bot = commands.Bot(command_prefix="Nonelol", intents=discord.Intents.all())
    await bot.login(token)
    asyncio.get_event_loop().create_task(bot.connect())
    await bot.wait_until_ready()

    database = DatabaseHelper()
    session = database.session_creator()
    db = MongoDB()
    client = db.client
    discord_db = client.discord
    messages = discord_db.messages
    before = perf_counter()
    # pipeline = [{
    #     "$group": {"_id": "$_id"}
    # }]
    # print("getting ids...")
    # aggregated = discord_db.guilds.aggregate(pipeline)
    # unique_list = await aggregated.to_list(length=None)
    # all_guild_ids = set(x.get("_id") for x in unique_list)
    # print("got ids...")
    # to_insert = []
    # query = session.query(Guild)
    # print("query ready...")
    # for guild in query:
    #     print(guild.id)
    #     if guild.id in all_guild_ids:
    #         continue
    #     print(guild)
        # guild_document = {"_id": guild.id, "name": guild.name, "removed": guild.removed}
        # channel_document = {"_id": channel.id, "name": channel.name, "guild_id": channel.guild.id}
        # to_insert.append(guild_document)
        # except json.decoder.JSONDecodeError:
        #     print(message.embed_json)
        #     message_document = {"_id": message.id, "channel_id": message.channel_id, "user_id": message.user_id,
        #                         "content": message.content, "created_at": message.timestamp,
        #                         "embeds": [],
        #                         "deleted": message.deleted, "edits": []}
    # print("inserting into mongo now")
    # result = await discord_db.guilds.insert_many(to_insert, ordered=False)
    # print(len(result.inserted_ids))
    known_channel_guild_ids = {}
    i = 0
    async for message in messages.find({"guild_id": None}):
        channel_id = message.get("channel_id")
        if channel_id in known_channel_guild_ids:
            guild_id = known_channel_guild_ids[channel_id]
        else:
            channel_in_db = await db.discord_db.channels.find_one({"_id": channel_id})
            if channel_in_db is None:
                try:
                    discord_channel = await bot.fetch_channel(channel_id)
                except discord.errors.NotFound:
                    continue
                guild_id = discord_channel.guild.id
            else:
                guild_id = channel_in_db.get("guild_id")
            #     known_channel_guild_ids[channel_id] = guild_id
        await messages.update_one({"_id": message.get("_id")}, {'$set': {"guild_id": guild_id}})
        i += 1
        if i % 50 == 0:
            print(i)
    # async for channel in channels.find():
    #     print(channel)
    #     channel_id = channel.get("_id")
    #     guild_id = channel.get("guild_id")
    #     await messages.update_many({"channel_id": channel_id}, {'$set': {"guild_id": guild_id}})
    # async for message in messages.find():
    #     channel_id = message.get("channel_id")
    #     if channel_id in known_channel_guild_ids:
    #         guild_id = known_channel_guild_ids[channel_id]
    #     else:
    #         channel_in_db = await db.discord_db.channels.find_one({"_id": channel_id})
    #         if channel_in_db is None:
    #             try:
    #                 discord_channel = await bot.fetch_channel(channel_id)
    #             except discord.errors.NotFound:
    #                 continue
    #             guild_id = discord_channel.guild.id
    #         else:
    #             guild_id = channel_in_db.get("guild_id")
    #     known_channel_guild_ids[channel_id] = guild_id
    #     await messages.update_one({"_id": message.get("_id")}, {'$set': {"guild_id": guild_id}})
    #     i += 1
    #     if i % 50 == 0:
    #         print(i)
    print(perf_counter() - before)


if __name__ == '__main__':
    loop = asyncio.get_event_loop()
    loop.create_task(main())
    loop.run_forever()
