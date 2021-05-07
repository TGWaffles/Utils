import discord

from discord.ext import commands, tasks
from typing import Optional
from main import UtilsBot
from src.checks.role_check import is_staff


class DynamicChannels(commands.Cog):
    def __init__(self, bot: UtilsBot):
        self.bot = bot
        self.dynamic_coll = self.bot.mongo.discord_db.dynamic_channels
        self.start_tasks = [self.update_message_count]
        for task in self.start_tasks:
            task.start()

    @commands.command()
    @is_staff()
    async def set_message_channel(self, ctx, channel: Optional[discord.VoiceChannel]):
        overwrites = {ctx.guild.default_role: discord.PermissionOverwrite(view_channel=True, connect=False),
                      ctx.guild.me: discord.PermissionOverwrite(view_channel=True, connect=True)}
        if channel is None:
            channel = await ctx.guild.create_voice_channel("Messages: Pending", overwrites=overwrites)
        channel_document = {"type": "message_count", "channel_id": channel.id}
        await self.bot.mongo.force_insert(self.dynamic_coll, channel_document)
        await ctx.reply(embed=self.bot.create_completed_embed("Set Channel as Message Count",
                                                              f"Set-up {channel.mention} as message count channel!"))

    @tasks.loop(seconds=600, count=None)
    async def update_message_count(self):
        async for channel_document in self.dynamic_coll.find({"type": "message_count"}):
            channel_id = channel_document.get("channel_id")
            channel = self.bot.get_channel(channel_id)
            if channel is None:
                continue
            count = await self.bot.mongo.discord_db.messages.count_documents({"guild_id": channel.guild.id,
                                                                              "deleted": False})
            await channel.edit(name=f"Messages: {count:,}")


def setup(bot: UtilsBot):
    cog = DynamicChannels(bot)
    bot.add_cog(cog)
