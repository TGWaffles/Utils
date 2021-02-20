import discord
import re

from discord.ext import commands

from main import UtilsBot


class Paginator:
    def __init__(self, bot: UtilsBot, channel: discord.TextChannel, title=None, full_text=None, caller=None):
        self.channel = channel
        self.title = title
        self.full_text = full_text
        self.caller = caller
        self.remaining_text = self.full_text
        self.page_index = 0
        self.pages = []
        self.message = None

    async def start(self):
        self.fill_pages()
        self.message = await self.channel.send()

    def fill_pages(self):
        while len(self.remaining_text) > 2000:
            newline_indices = [m.end() for m in re.finditer(r"\n", self.remaining_text[:2000])]
            if len(newline_indices) == 0:
                space_indices = [m.end() for m in re.finditer(r"\s", self.remaining_text[:2000])]
                if len(space_indices) == 0:
                    self.pages.append(self.remaining_text[:2000])
                    self.remaining_text = self.remaining_text[2000:]
                else:
                    self.pages.append(self.remaining_text[:space_indices[-1]])
                    self.remaining_text = self.remaining_text[space_indices[-1]:]
            else:
                self.pages.append(self.remaining_text[:newline_indices[-1]])
                self.remaining_text = self.remaining_text[newline_indices[-1]:]

        if self.remaining_text != "":
            self.pages.append(self.remaining_text)
        return True

    def create_page(self, page):
        embed = discord.Embed(title=self.title)
