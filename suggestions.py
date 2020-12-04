import config
import discord
import messages

from discord.ext import commands
from main import UtilsBot


class Suggestions(commands.Cog):
    def __init__(self, bot: UtilsBot):
        self.bot: UtilsBot = bot
        self.suggestions_channel: discord.TextChannel = self.bot.get_channel(config.suggestions_channel_id)
        self.decisions_channel: discord.TextChannel = self.bot.get_channel(config.suggestions_decisions_id)

    async def handle_channel_message(self, message):
        if not message.content.lower().startswith("suggest "):
            await message.channel.send(embed=self.bot.create_error_embed(
                messages.new_suggestion_format.format(message.author.mention)), delete_after=10.0)
        await self.create_suggestion(message.content.partition(" ")[2], message.author)
        await message.delete()

    async def create_suggestion(self, suggestion, author):
        suggestion_embed = discord.Embed(title="New User Suggestion", description=suggestion,
                                         colour=discord.Colour.from_rgb(26, 188, 156))
        suggestion_embed.add_field(name="Author", value="{}: {}".format(author.mention, author.id), inline=True)
        suggestion_embed.add_field(name="Reviewed", value="Not yet!", inline=True)
        suggestion_embed.add_field(name="Status", value="Not Reviewed", inline=False)
        suggestion_embed.add_field(name="Suggestion ID", value="Processing...", inline=False)
        sent_message = await self.suggestions_channel.send(embed=suggestion_embed)
        suggestion_embed.set_field_at(3, name="Suggestion ID", value=sent_message.id, inline=False)
        await sent_message.edit(embed=suggestion_embed)
        await sent_message.add_reaction("✅")
        await sent_message.add_reaction("❌")

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.channel == self.suggestions_channel:
            await self.handle_channel_message(message)
