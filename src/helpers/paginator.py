import re

import discord

from main import UtilsBot
from src.storage import config


class Paginator:
    def __init__(self, bot: UtilsBot, channel: discord.TextChannel, title=None, full_text=None, max_length=2000,
                 reply_message=None):
        self.bot = bot
        self.reply_message = reply_message
        self.channel = channel
        self.title = title
        self.full_text = full_text
        self.remaining_text = self.full_text
        self.length = max_length
        self.page_index = 0
        self.pages = []
        self.message = None

    async def start(self):
        self.fill_pages()
        if self.reply_message is None:
            self.message = await self.channel.send(embed=self.create_page())
        else:
            self.message = await self.reply_message.reply(embed=self.create_page())
        await self.message.add_reaction(config.rewind_emoji)
        await self.message.add_reaction(config.fast_forward_emoji)
        self.bot.add_listener(self.on_raw_reaction_add, "on_raw_reaction_add")

    async def on_raw_reaction_add(self, payload: discord.RawReactionActionEvent):
        if (payload.message_id != self.message.id or payload.event_type != "REACTION_ADD"
                or payload.member.id == self.bot.user.id):
            return
        await self.message.remove_reaction(payload.emoji, payload.member)
        if str(payload.emoji) == config.fast_forward_emoji:
            if self.page_index >= len(self.pages) - 1:
                return
            self.page_index += 1
        elif str(payload.emoji) == config.rewind_emoji:
            if self.page_index <= 0:
                return
            self.page_index -= 1
        await self.update_message()

    def fill_pages(self):
        while len(self.remaining_text) > self.length:
            newline_indices = [m.end() for m in re.finditer(r"\n", self.remaining_text[:self.length])]
            if len(newline_indices) == 0:
                space_indices = [m.end() for m in re.finditer(r"\s", self.remaining_text[:self.length])]
                if len(space_indices) == 0:
                    self.pages.append(self.remaining_text[:self.length])
                    self.remaining_text = self.remaining_text[self.length:]
                else:
                    self.pages.append(self.remaining_text[:space_indices[-1]])
                    self.remaining_text = self.remaining_text[space_indices[-1]:]
            else:
                self.pages.append(self.remaining_text[:newline_indices[-1]])
                self.remaining_text = self.remaining_text[newline_indices[-1]:]

        if self.remaining_text != "":
            self.pages.append(self.remaining_text)
        return True

    async def update_message(self):
        await self.message.edit(embed=self.create_page())

    def create_page(self):
        embed = discord.Embed(title=self.title, colour=discord.Colour.orange())
        embed.description = self.pages[self.page_index]
        return embed
