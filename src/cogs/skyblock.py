from concurrent.futures import ProcessPoolExecutor
from functools import partial
from io import BytesIO

import discord
from discord.ext import commands

from main import UtilsBot
from src.helpers.graph_helper import plot_multiple
from src.helpers.paginator import Paginator


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

    async def auctions_from_names(self, names):
        pipeline = [
            {
                "$match": {
                    "item_name": {
                        "$in": names
                    },
                    "bin": True
                }
            },
            {
                "$unwind": "$updates"
            },
            {
                "$group": {
                    "_id": "$updates",
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
            },
            {
                "$lookup": {
                    "from": "auction_updates",
                    "localField": "_id",
                    "foreignField": "_id",
                    "as": "auction"
                }
            },
            {
                "$project": {
                    "_id": "$auction.timestamp",
                    "minimum": 1,
                    "average": 1,
                    "maximum": 1
                }
            },
            {
                "$unwind": "$_id"
            }
        ]
        auctions = await self.skyblock_db.auctions.aggregate(pipeline=pipeline).to_list(length=None)
        return auctions

    async def get_item_from_name(self, item_names):
        minimum_prices = []
        average_prices = []
        maximum_prices = []
        for auction in await self.auctions_from_names(item_names):
            minimum_prices.append((auction["_id"], auction["minimum"]))
            average_prices.append((auction["_id"], auction["average"]))
            maximum_prices.append((auction["_id"], auction["maximum"]))
        minimum_prices.sort(key=lambda x: x[0])
        average_prices.sort(key=lambda x: x[0])
        maximum_prices.sort(key=lambda x: x[0])
        return minimum_prices, average_prices, maximum_prices

    async def get_item_data(self, query, enchant_id=None, level=None):
        minimum_prices = []
        average_prices = []
        maximum_prices = []
        for auction in await self.get_bin_auctions(query, enchant_id, level):
            minimum_prices.append((auction["_id"], auction["minimum"]))
            average_prices.append((auction["_id"], auction["average"]))
            maximum_prices.append((auction["_id"], auction["maximum"]))
        minimum_prices.sort(key=lambda x: x[0])
        average_prices.sort(key=lambda x: x[0])
        maximum_prices.sort(key=lambda x: x[0])
        return minimum_prices, average_prices, maximum_prices

    async def book_extract(self, ctx, query):
        level = query.split(" ")[-1]
        try:
            level = int(level)
            enchant_name = " ".join(query.split(" ")[:-1])
        except ValueError:
            enchant_name = query
            level = None
        enchantment_document = await self.skyblock_db.enchantments.find_one({"$text": {"$search": enchant_name}})
        if enchantment_document is None:
            await ctx.reply(embed=self.bot.create_error_embed(f"I couldn't find a matching enchantment "
                                                              f"for `{enchant_name}`!"))
            raise ValueError
        return await self.get_item_data("Enchanted Book", enchantment_document["_id"], level)

    @book.command(name="history")
    async def book_history(self, ctx, *, query):
        query = query.lower()
        async with ctx.typing():
            try:
                minimum_prices, average_prices, maximum_prices = await self.book_extract(ctx, query)
            except ValueError:
                return
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
            try:
                minimum_prices, average_prices, maximum_prices = await self.book_extract(ctx, query)
            except ValueError:
                return
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
            try:
                minimum_prices, average_prices, maximum_prices = await self.book_extract(ctx, query)
            except ValueError:
                return
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

    async def auctions_from_query(self, query, enchant_id=None, level=None):
        pipeline = [
            {
                "$match": {
                    "$text": {"$search": f"{query}"}
                }
            },
            {
                "$unwind": "$updates"
            },
            {
                "$group": {
                    "_id": "$updates",
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
            },
            {
                "$lookup": {
                    "from": "auction_updates",
                    "localField": "_id",
                    "foreignField": "_id",
                    "as": "auction"
                }
            },
            {
                "$project": {
                    "_id": "$auction.timestamp",
                    "minimum": 1,
                    "average": 1,
                    "maximum": 1
                }
            },
            {
                "$unwind": "$_id"
            }
        ]
        match_dict = {"bin": True,
                      "item_name": {
                          "$regex": f".*{query}.*",
                          "$options": 'i'}}

        if enchant_id is not None:
            match_dict["item_name"] = "Enchanted Book"
            match_dict["enchantments.enchantment"] = enchant_id
            if level is not None:
                match_dict["enchantments.level"] = level
            pipeline[0] = {
                "$match": match_dict
            }
        else:
            final_match = {
                "$match": match_dict
            }
            pipeline.insert(1, final_match)
        auctions = await self.skyblock_db.auctions.aggregate(pipeline=pipeline).to_list(length=None)
        return auctions

    async def get_bin_auctions(self, query, enchant_id=None, level=None):
        return await self.auctions_from_query(query, enchant_id, level)

    @skyblock.command()
    async def history(self, ctx, *, query):
        async with ctx.typing():
            minimum_prices, average_prices, maximum_prices = await self.get_item_data(query)
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
            minimum_prices, average_prices, maximum_prices = await self.get_item_data(query)
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

    async def ask_name(self, ctx, query):
        all_names = await self.skyblock_db.auctions.distinct("item_name")
        valid_names = [x for x in all_names if query.lower() in x]
        if len(valid_names) == 0:
            await ctx.reply(embed=self.bot.create_error_embed("I couldn't find any items matching that name!"))
            ctx.kwargs["resolved"] = True
            raise commands.BadArgument()
        item_choice_text = "Are any of these the item you want? Enter the index of the item.\n0. Any Item\n"
        for index, optional_item_name in enumerate(valid_names):
            item_choice_text += f"{index + 1}. {optional_item_name}\n"
        paginator = Paginator(self.bot, None, title="Choose an item", full_text=item_choice_text, max_length=500,
                              reply_message=ctx)
        await paginator.start()
        item_index = await self.bot.ask_question(ctx, None)
        try:
            item_index = int(item_index)
        except ValueError:
            await ctx.reply(embed=self.bot.create_error_embed("Invalid index! Please enter a valid number. "
                                                              "Search cancelled."))
            ctx.kwargs["resolved"] = True
            raise commands.BadArgument()
        if item_index != 0:
            valid_names = [valid_names[item_index - 1]]
        if len(valid_names) == 0:
            await ctx.reply(embed=self.bot.create_error_embed("I couldn't find any items matching that name!"))
            ctx.kwargs["resolved"] = True
            raise commands.BadArgument()
        return valid_names

    @skyblock.command()
    async def minimum(self, ctx, *, query):
        async with ctx.typing():
            valid_names = await self.ask_name(ctx, query)
            minimum_prices, average_prices, maximum_prices = await self.get_item_from_name(valid_names)
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
