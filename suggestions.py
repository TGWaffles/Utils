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
            return
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

    async def handle_decision_message(self, message):
        if not message.content.lower().startswith("accept") and not message.content.lower().startswith("deny"):
            return
        accepted = int(message.content.startswith("accept"))
        message_to_send = messages.suggestion_changed
        try:
            suggestion_id = int(message.content.split(" ")[1])
        except ValueError:
            await message.channel.send(messages.invalid_message_id.format(message.content.split(" ")[1]))
            return
        try:
            suggestion_message = await self.suggestions_channel.fetch_message(suggestion_id)
        except discord.NotFound:
            await message.channel.send(messages.id_not_found)
            return
        if suggestion_message.author.id != self.bot.user.id:
            await message.channel.send(messages.bot_not_author)
            return
        if len(suggestion_message.embeds) < 1:
            await message.channel.send(messages.no_embed)
            return
        reason = message.content.partition(" ")[2].partition(" ")[2]
        positive_reaction = [x for x in suggestion_message.reactions if str(x.emoji) == "✅"][0]
        suggestion_embed: discord.Embed = suggestion_message.embeds[0]
        message_to_send = message_to_send.format(suggestion_embed.description, ("denied", "accepted")[accepted],
                                                 message.author.mention, reason)
        if len(suggestion_embed.fields) == 4:
            suggestion_embed.insert_field_at(0, name="------------{}------------"
                                             .format(("DENIED", "ACCEPTED")[accepted]),
                                             value="Reason: {}".format(reason), inline=False)
        else:
            suggestion_embed.set_field_at(0, name="------------{}------------"
                                          .format(("DENIED", "ACCEPTED")[accepted]),
                                          value="Reason: {}".format(reason), inline=False)
        author_id = int(suggestion_embed.fields[1].value.split(": ")[-1])
        suggestion_embed.set_field_at(2, name="Reviewed?", value="**{}** by {}".format(
            ("Denied", "Accepted")[accepted],
            message.author.mention), inline=True)
        suggestion_embed.set_field_at(3, name="Status", value=("Denied.", "Accepted!")[accepted], inline=False)
        suggestion_embed.colour = (discord.Colour.red(), discord.Colour.green())[accepted]
        await suggestion_message.edit(embed=suggestion_embed)
        send_to_author = await self.send_acceptance_messages(positive_reaction.users, message_to_send, author_id)
        if send_to_author:
            try:
                await self.bot.get_user(author_id).send(message_to_send)
            except Exception as e:
                await self.bot.error_channel.send(embed=self.bot.create_error_embed(e))

        await message.channel.send(messages.suggestion_channel_feedback.format(suggestion_embed.description,
                                                                               ("Denied.", "Accepted!")[accepted],
                                                                               reason))

    async def send_acceptance_messages(self, users_generator, text, author_id):
        async for user in users_generator():
            if user.id != self.bot.user.id:
                if user.id == author_id:
                    author_id = None
                await user.send(text)
        if author_id is None:
            return True
        return False

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.channel == self.suggestions_channel:
            await self.handle_channel_message(message)

        elif message.channel == self.decisions_channel:
            await self.handle_decision_message(message)
