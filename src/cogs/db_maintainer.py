import discord
from discord.ext import commands

from main import UtilsBot


class DBMaintainer(commands.Cog):
    def __init__(self, bot: UtilsBot):
        self.bot = bot
        self.bot.loop.create_task(self.post_init())

    async def post_init(self):
        for guild in self.bot.guilds:
            await self.bot.mongo.insert_guild(guild)
            for channel in guild.text_channels:
                await self.bot.mongo.insert_channel(channel)
            for member in guild.members:
                await self.bot.mongo.insert_member(member)

    @commands.Cog.listener()
    async def on_message(self, message):
        if isinstance(message.channel, discord.DMChannel) or message.channel.guild is None or \
                not isinstance(message.author, discord.Member):
            return
        if bool(message.flags.value & 1 << 6):  # If message is ephemeral
            return
        await self.bot.mongo.insert_message(message)

    @commands.Cog.listener()
    async def on_raw_message_delete(self, payload: discord.RawMessageDeleteEvent):
        await self.bot.mongo.discord_db.messages.update_one({"_id": payload.message_id},
                                                            {'$set': {"deleted": True}})

    @commands.Cog.listener()
    async def on_raw_bulk_message_delete(self, payload: discord.RawBulkMessageDeleteEvent):
        message_ids = list(payload.message_ids)
        await self.bot.mongo.discord_db.messages.update_many({"_id": {'$in': message_ids}},
                                                             {'$set': {"deleted": True}})

    @commands.Cog.listener()
    async def on_raw_message_edit(self, payload: discord.RawMessageUpdateEvent):
        await self.bot.mongo.message_edit(payload)

    @commands.Cog.listener()
    async def on_member_remove(self, member: discord.Member):
        await self.bot.mongo.discord_db.members.update_one({"_id": {"user_id": member.id, "guild_id": member.guild.id}},
                                                           {'$set': {"deleted": True}})

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        if not isinstance(member, discord.Member):
            return
        await self.bot.mongo.insert_member(member)

    @commands.Cog.listener()
    async def on_member_update(self, _, after):
        await self.bot.mongo.insert_member(after)

    @commands.Cog.listener()
    async def on_user_update(self, _, after):
        await self.bot.mongo.insert_user(after)

    @commands.Cog.listener()
    async def on_guild_channel_update(self, _, after):
        if isinstance(after, discord.TextChannel):
            await self.bot.mongo.insert_channel(after)

    @commands.Cog.listener()
    async def on_guild_channel_delete(self, channel):
        if isinstance(channel, discord.TextChannel):
            await self.bot.mongo.discord_db.channels.update_one({"_id": channel.id},
                                                                {'$set': {"deleted": True}})

    @commands.Cog.listener()
    async def on_guild_channel_create(self, channel):
        if isinstance(channel, discord.TextChannel):
            await self.bot.mongo.insert_channel(channel)

    @commands.Cog.listener()
    async def on_guild_join(self, guild):
        await self.bot.mongo.insert_guild(guild)
        channels = await guild.fetch_channels()
        for channel in channels:
            if isinstance(channel, discord.TextChannel):
                await self.bot.mongo.insert_channel(channel)
        async for member in guild.fetch_members(limit=None):
            await self.bot.mongo.insert_member(member)

    @commands.Cog.listener()
    async def on_guild_update(self, _, guild):
        await self.bot.mongo.insert_guild(guild)


def setup(bot: UtilsBot):
    cog = DBMaintainer(bot)
    bot.add_cog(cog)
