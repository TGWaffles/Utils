import re

import discord

from main import UtilsBot
from src.storage import config
from typing import Optional


class BasePaginator:
    def __init__(self, bot: UtilsBot, channel: Optional[discord.TextChannel], reply_message: discord.Message,
                 file=None):
        self.file = file
        self.reply_message = reply_message
        self.channel = channel
        self.page_index = 0
        self.bot = bot
        self.message = None
        self.pages = []

    async def start(self):
        if self.reply_message is None:
            self.message = await self.channel.send(embed=self.create_page(), file=self.file)
        else:
            self.message = await self.reply_message.reply(embed=self.create_page(), file=self.file)
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

    def create_page(self):
        raise NotImplementedError()

    async def update_message(self):
        raise NotImplementedError()


class Paginator(BasePaginator):
    def __init__(self, bot: UtilsBot, channel: Optional[discord.TextChannel], title=None, full_text=None,
                 max_length=2000, reply_message=None):
        super().__init__(bot, channel, reply_message)
        self.title = title
        self.full_text = full_text
        self.remaining_text = self.full_text
        self.length = max_length
        self.page_index = 0
        self.pages = []
        self.message = None

    def add_line(self):
        self.full_text += "\n"

    def close_page(self):
        pass

    def clear(self):
        self.full_text = ""

    async def start(self):
        self.fill_pages()
        await super().start()

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


class EmbedPaginator(BasePaginator):
    def __init__(self, bot: UtilsBot, channel: Optional[discord.TextChannel], embeds: list[discord.Embed],
                 reply_message=None, file: discord.File = None):
        super().__init__(bot, channel, reply_message, file=file)
        self.page_index = 0
        self.pages: list[discord.Embed] = embeds
        self.files = None
        self.message = None

    async def update_message(self):
        await self.message.edit(embed=self.create_page())

    def create_page(self):
        embed = self.pages[self.page_index]
        return embed
