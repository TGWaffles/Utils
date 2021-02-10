from src.storage import config, messages
import discord
import datetime

from discord.ext import commands, tasks
from main import UtilsBot
from src.checks.role_check import is_staff, is_staff_backend
from src.checks.guild_check import monkey_check


class Suggestions(commands.Cog):
    def __init__(self, bot: UtilsBot):
        self.bot: UtilsBot = bot
        self.suggestions_channel: discord.TextChannel = self.bot.get_channel(config.suggestions_channel_id)
        self.decisions_channel: discord.TextChannel = self.bot.get_channel(config.suggestions_decisions_id)
        self.archive_channel: discord.TextChannel = self.bot.get_channel(config.archive_channel_id)
        self.allow_messages = False
        self.check_suggestions.start()

    async def handle_channel_message(self, message):
        if not message.content.lower().startswith("suggest "):
            if self.allow_messages and is_staff():
                return
            await message.reply(embed=self.bot.create_error_embed(
                messages.new_suggestion_format.format(message.author.mention)), delete_after=10.0)
            await message.delete()
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
        suggestion_embed.set_author(name=author.name,
                                    icon_url="https://cdn.discordapp.com/emojis/787036714337566730.png")
        await sent_message.edit(embed=suggestion_embed)
        await sent_message.add_reaction("✅")
        await sent_message.add_reaction("❌")

    async def handle_decision_message(self, message):
        if not message.content.lower().startswith("accept") and not message.content.lower().startswith("deny"):
            return
        accepted = int(message.content.lower().startswith("accept"))
        message_to_send = messages.suggestion_changed
        if message.reference is not None:
            try:
                _ = int(message.content.split(" ")[1])
                reason = message.content.partition(" ")[2].partition(" ")[2]
            except ValueError:
                reason = message.content.partition(" ")[2]
            suggestion_id = message.reference.message_id
        else:
            try:
                suggestion_id = int(message.content.split(" ")[1])
                reason = message.content.partition(" ")[2].partition(" ")[2]
            except ValueError:
                await message.reply(messages.invalid_message_id.format(message.content.split(" ")[1]))
                return
        try:
            suggestion_message = await self.suggestions_channel.fetch_message(suggestion_id)
        except discord.NotFound:
            await message.reply(messages.id_not_found)
            return
        if suggestion_message.author.id != self.bot.user.id:
            await message.reply(messages.bot_not_author)
            return
        if len(suggestion_message.embeds) < 1:
            await message.reply(messages.no_embed)
            return
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
        suggestion_embed.set_author(name=self.bot.get_user(author_id).name,
                                    icon_url=("https://cdn.discordapp.com/emojis/787035973287542854.png",
                                              "https://cdn.discordapp.com/emojis/787034785583333426.png")[accepted])
        suggestion_embed.colour = (discord.Colour.red(), discord.Colour.green())[accepted]
        suggestion_embed.timestamp = datetime.datetime.utcnow()
        await suggestion_message.edit(embed=suggestion_embed)
        send_to_author = await self.send_acceptance_messages(positive_reaction.users, message_to_send, author_id)
        if send_to_author:
            try:
                await self.bot.get_user(author_id).send(message_to_send)
            except Exception as e:
                await self.bot.error_channel.send(embed=self.bot.create_error_embed(e))

        sent_message = await message.reply(messages.suggestion_channel_feedback.format(suggestion_embed.description,
                                                                                       ("Denied.", "Accepted!")[
                                                                                           accepted],
                                                                                       reason))
        await sent_message.delete(delay=20)
        await message.delete(delay=20)
        return True

    async def send_acceptance_messages(self, users_generator, text, author_id):
        async for user in users_generator():
            if user.id != self.bot.user.id and user.id != config.lexi_id:
                if user.id == author_id:
                    author_id = None
                try:
                    await user.send(text)
                except discord.errors.Forbidden:
                    pass
        if author_id is None:
            return True
        return False

    @commands.Cog.listener()
    @monkey_check()
    async def on_message(self, message):
        if message.author.bot or message.channel not in \
                (self.decisions_channel, self.suggestions_channel, self.archive_channel):
            return
        return_val = None
        if message.channel == self.decisions_channel and is_staff_backend(message.author):
            return_val = await self.handle_decision_message(message)
        if message.channel == self.suggestions_channel and return_val is None:
            await self.handle_channel_message(message)

    # noinspection SpellCheckingInspection,PyUnusedLocal
    @commands.command(pass_context=True)
    @is_staff()
    @monkey_check()
    async def allowtext(self, ctx):
        self.allow_messages = not self.allow_messages

    @tasks.loop(seconds=30)
    async def check_suggestions(self):
        async for message in self.suggestions_channel.history(oldest_first=True, limit=None):
            if len(message.embeds) == 0:
                continue
            embed = message.embeds[0]
            if embed.timestamp != discord.Embed.Empty:
                if (datetime.datetime.utcnow() - embed.timestamp).days >= 1:
                    plus_reactions = [reaction for reaction in message.reactions if reaction.emoji == "✅"][0].count - 1
                    negative_reactions = [reaction for reaction in message.reactions
                                          if reaction.emoji == "❌"][0].count - 1
                    embed.add_field(name="✅", value=plus_reactions, inline=True)
                    embed.add_field(name="❌", value=negative_reactions, inline=True)
                    await self.archive_channel.send(embed=embed)
                    await message.delete()
                else:
                    continue


def setup(bot):
    cog = Suggestions(bot)
    bot.add_cog(cog)
