import asyncio
import homoglyphs as hg

from discord.ext import commands
from unidecode import unidecode

from main import UtilsBot
from src.checks.role_check import is_staff, is_staff_backend
from src.helpers.storage_helper import DataHelper
from src.storage import config


class Blacklist(commands.Cog):
    def __init__(self, bot: UtilsBot):
        self.bot: UtilsBot = bot
        self.data = DataHelper()

    @staticmethod
    def remove_obfuscation(input_string: str):
        return unidecode(input_string.replace(" ", "")).lower()

    @commands.command()
    @is_staff()
    async def blacklist(self, ctx, *, words: str):
        words = self.remove_obfuscation(words)
        all_guilds = self.data.get("blacklist", {})
        this_guild_words = all_guilds.get(str(ctx.guild.id), [])
        if words not in this_guild_words:
            this_guild_words.append(words)
            await ctx.reply(embed=self.bot.create_completed_embed("Added!", "Added that word to blacklist."))
        else:
            this_guild_words.remove(words)
            await ctx.reply(embed=self.bot.create_completed_embed("Removed!", "Removed that word from blacklist."))
        all_guilds[str(ctx.guild.id)] = this_guild_words
        self.data["blacklist"] = all_guilds

    async def blacklist_check(self, message):
        def check(m):
            return m.author.id == config.lexibot_id and m.channel.id == message.channel.id
        try:
            await self.bot.wait_for("message", check=check, timeout=0.6)
            return
        except asyncio.TimeoutError:
            pass
        content = message.content
        content = self.remove_obfuscation(content)
        all_guilds = self.data.get("blacklist", {})
        this_guild_words = all_guilds.get(str(message.guild.id), [])
        for word in this_guild_words:
            if word in content:
                await message.delete()
                # sent = await message.channel.send("~warn {} Bad word usage.".format(message.author.mention))
                # try:
                #     await self.bot.wait_for("message", check=check, timeout=10)
                # except asyncio.TimeoutError:
                #     pass
                # await sent.delete()
                return

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.guild is None or message.author.bot or is_staff_backend(message.author):
            return

        await self.blacklist_check(message)
        # if message.author.bot:
        #     return
        # print("running blacklist check...")
        # if (config.staff_role_id in [role.id for role in message.author.roles] or
        #         message.author.guild_permissions.administrator):
        #     return
        # contents: str = message.content
        # print(''.join(filter(str.isalpha, contents)))
        # if "cantswim" in ''.join(filter(str.isalpha, contents)):
        #     print("it's in...")
        #     await message.delete()

    @commands.Cog.listener()
    async def on_message_edit(self, before, after):
        message = after
        if message.guild is None or message.author.bot or is_staff_backend(message.author):
            return

        await self.blacklist_check(message)


def setup(bot):
    cog = Blacklist(bot)
    bot.add_cog(cog)

