import asyncio
import discord
import motor.motor_asyncio
import aiohttp


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
        guild_document = {"_id": guild.id, "name": guild.name}
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
            assert isinstance(member, discord.User)
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
        message_document = {"_id": message.id, "channel_id": message.channel_id, "user_id": message.author.id,
                            "content": message.content, "created_at": message.created_at,
                            "embeds": [embed.to_dict() for embed in message.embeds]}
        await self.force_insert(self.discord_db.messages, message_document)

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
    db = MongoDB()
    client = db.client
    hypixel = client.hypixel
    channels = hypixel.channels

    # print(await db.find_by_id(channels, 798292125027926036))
    print(await channels.find_one({"_id": "nothing"}))
    # print([await db.username_from_uuid(uuid) for uuid in await channels.distinct("players")])


if __name__ == '__main__':
    loop = asyncio.get_event_loop()
    loop.create_task(main())
    loop.run_forever()