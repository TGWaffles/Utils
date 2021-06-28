import asyncio
from functools import partial
from io import BytesIO
from statistics import mean

import discord
import gc
from discord.ext import commands
from concurrent.futures import ProcessPoolExecutor

from main import UtilsBot
from src.helpers.graph_helper import plot_multiple


class Skyblock(commands.Cog):
    def __init__(self, bot: UtilsBot):
        self.bot: UtilsBot = bot
        self.skyblock_db = self.bot.mongo.client.skyblock

    @commands.group(case_insensitive=True)
    async def skyblock(self, ctx):
        if ctx.invoked_subcommand is None:
            await ctx.reply(embed=self.bot.create_error_embed("Invalid format! "
                                                              "Please specify a subcommand. Valid "
                                                              "subcommands: `history`, `average`, `minimum`, `book`"))

    @skyblock.group(case_insensitive=True)
    async def book(self, ctx):
        if ctx.invoked_subcommand is None:
            await ctx.reply(embed=self.bot.create_error_embed("Invalid format! "
                                                              "Please specify a subcommand. Valid "
                                                              "subcommands: `history`, `average`, `minimum`"))

    async def get_item_data(self, query, book=False):
        minimum_prices = []
        average_prices = []
        maximum_prices = []
        for auction in await self.get_bin_auctions(query, book=book):
            minimum_prices.append((auction["_id"], auction["minimum"]))
            average_prices.append((auction["_id"], auction["average"]))
            maximum_prices.append((auction["_id"], auction["maximum"]))
        minimum_prices.sort(key=lambda x: x[0])
        average_prices.sort(key=lambda x: x[0])
        maximum_prices.sort(key=lambda x: x[0])
        return minimum_prices, average_prices, maximum_prices

    @book.command(name="history")
    async def book_history(self, ctx, *, query):
        query = query.lower()
        async with ctx.typing():
            minimum_prices, average_prices, maximum_prices = await self.get_item_data(query, True)
            if len(maximum_prices) == 0:
                await ctx.reply(embed=self.bot.create_error_embed("No auctions could be found."))
                return
            with ProcessPoolExecutor() as pool:
                data = await self.bot.loop.run_in_executor(pool, partial(plot_multiple,
                                                                         title=f"Prices for {query} books",
                                                                         x_label="Date",
                                                                         y_label="Price in coins",
                                                                         Minimum=minimum_prices,
                                                                         Average=average_prices,
                                                                         Maximum=maximum_prices))
            file = BytesIO(data)
            file.seek(0)
            discord_file = discord.File(fp=file, filename="image.png")
            await ctx.reply(file=discord_file)

    @book.command(name="average")
    async def book_average(self, ctx, *, query):
        query = query.lower()
        async with ctx.typing():
            minimum_prices, average_prices, maximum_prices = await self.get_item_data(query, True)
            if len(maximum_prices) == 0:
                await ctx.reply(embed=self.bot.create_error_embed("No auctions could be found."))
                return
            with ProcessPoolExecutor() as pool:
                data = await self.bot.loop.run_in_executor(pool, partial(plot_multiple,
                                                                         title=f"Average prices for {query} books",
                                                                         x_label="Date",
                                                                         y_label="Price in coins",
                                                                         Minimum=minimum_prices,
                                                                         Average=average_prices))
            file = BytesIO(data)
            file.seek(0)
            discord_file = discord.File(fp=file, filename="image.png")
            await ctx.reply(file=discord_file)

    @book.command(name="minimum")
    async def book_average(self, ctx, *, query):
        query = query.lower()
        async with ctx.typing():
            minimum_prices, average_prices, maximum_prices = await self.get_item_data(query, True)
            if len(maximum_prices) == 0:
                await ctx.reply(embed=self.bot.create_error_embed("No auctions could be found."))
                return
            with ProcessPoolExecutor() as pool:
                data = await self.bot.loop.run_in_executor(pool, partial(plot_multiple,
                                                                         title=f"Minimum prices for {query} books",
                                                                         x_label="Date",
                                                                         y_label="Price in coins",
                                                                         Minimum=minimum_prices))
            file = BytesIO(data)
            file.seek(0)
            discord_file = discord.File(fp=file, filename="image.png")
            await ctx.reply(file=discord_file)

    async def auctions_from_query(self, query, item_lore=None):
        pipeline = [
            {
                "$match": {
                    "$text": {"$search": f"{query}"}
                }
            },
            {
                "$lookup": {
                    "from": "auctions",
                    "localField": "_id.auction_id",
                    "foreignField": "_id",
                    "as": "auction"
                }
            },
            {
                "$project": {
                    "_id": 0,
                    "auctions": 1,
                    "auction": 1
                }
            },
            {
                "$unwind": "$auctions"
            },
            {
                "$addFields": {
                    "auctions.timestamp": "$auction.timestamp"
                }
            },
            {
                "$replaceWith": "$auctions"
            }
        ]
        add_after = [{
            "$unwind": "$timestamp"
            },
            {
                "$group": {
                    "_id": "$timestamp",
                    "minimum": {
                        "$min": "$starting_bid"
                    },
                    "average": {
                        "$avg": "$starting_bid"
                    },
                    "maximum": {
                        "$max": "$starting_bid"
                    }
                }
            }
        ]
        final_match = {
            "$match": {
                "bin": True,
                "item_name": {
                    "$regex": f".*{query}.*",
                    "$options": 'i'
                }
            }
        }
        if item_lore is not None:
            final_match = {
                "$match": {
                    "bin": True,
                    "item_name": {
                        "$regex": f".*{query}.*",
                        "$options": 'i'
                    },
                    "item_lore": {
                        "$regex": f".*{item_lore}.*",
                        "$options": 'i'
                    }
                }
            }
        pipeline.append(final_match)
        pipeline += add_after
        print(pipeline)
        auctions = await self.skyblock_db.auction_pages.aggregate(pipeline=pipeline).to_list(length=None)
        return auctions

    async def get_bin_auctions(self, query, book=False):
        if book:
            lore_query = query
            query = "enchanted book"
            return await self.auctions_from_query(query, item_lore=lore_query)
        else:
            return await self.auctions_from_query(query)

    @skyblock.command()
    async def history(self, ctx, *, query):
        async with ctx.typing():
            minimum_prices, average_prices, maximum_prices = await self.get_item_data(query, False)
            if len(maximum_prices) == 0:
                await ctx.reply(embed=self.bot.create_error_embed("No auctions could be found."))
                return
            with ProcessPoolExecutor() as pool:
                data = await self.bot.loop.run_in_executor(pool, partial(plot_multiple,
                                                                         title=f"Prices for {query}",
                                                                         x_label="Date",
                                                                         y_label="Price in coins",
                                                                         Minimum=minimum_prices,
                                                                         Average=average_prices,
                                                                         Maximum=maximum_prices))
            file = BytesIO(data)
            file.seek(0)
            discord_file = discord.File(fp=file, filename="image.png")
            await ctx.reply(file=discord_file)

    @skyblock.command()
    async def average(self, ctx, *, query):
        async with ctx.typing():
            minimum_prices, average_prices, maximum_prices = await self.get_item_data(query, False)
            if len(maximum_prices) == 0:
                await ctx.reply(embed=self.bot.create_error_embed("No auctions could be found."))
                return
            with ProcessPoolExecutor() as pool:
                data = await self.bot.loop.run_in_executor(pool, partial(plot_multiple,
                                                                         title=f"Average prices for {query}",
                                                                         x_label="Date",
                                                                         y_label="Price in coins",
                                                                         Minimum=minimum_prices,
                                                                         Average=average_prices))
            file = BytesIO(data)
            file.seek(0)
            discord_file = discord.File(fp=file, filename="image.png")
            await ctx.reply(file=discord_file)

    @skyblock.command()
    async def minimum(self, ctx, *, query):
        async with ctx.typing():
            minimum_prices, average_prices, maximum_prices = await self.get_item_data(query, False)
            if len(maximum_prices) == 0:
                await ctx.reply(embed=self.bot.create_error_embed("No auctions could be found."))
                return
            with ProcessPoolExecutor() as pool:
                data = await self.bot.loop.run_in_executor(pool, partial(plot_multiple,
                                                                         title=f"Minimum prices for {query}",
                                                                         x_label="Date",
                                                                         y_label="Price in coins",
                                                                         Minimum=minimum_prices))
            file = BytesIO(data)
            file.seek(0)
            discord_file = discord.File(fp=file, filename="image.png")
            await ctx.reply(file=discord_file)


def setup(bot):
    cog = Skyblock(bot)
    bot.add_cog(cog)
