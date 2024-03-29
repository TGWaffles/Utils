import asyncio
import datetime
from collections import defaultdict
from concurrent.futures import ProcessPoolExecutor
from functools import partial
from io import BytesIO

import discord
from discord.ext import commands

from main import UtilsBot
from src.helpers.graph_helper import plot_multiple, tfm_graph
from src.helpers.models.skyblock_models import Rarity
from src.helpers.paginator import Paginator

PROFITS_START_DATE = datetime.datetime(2021, 12, 14, 0, 0, 0, tzinfo=datetime.timezone.utc)
FLIPS_START_DATE = datetime.datetime(2022, 1, 12, 21, 0, 0, tzinfo=datetime.timezone.utc)


class Skyblock(commands.Cog):
    def __init__(self, bot: UtilsBot):
        self.bot: UtilsBot = bot
        self.skyblock_db = self.bot.mongo.client.skyblock
        self.cached_graphs = defaultdict(bytes)
        self.last_cached_time = defaultdict(lambda: datetime.datetime(2021, 12, 14, 0, 0, 0,
                                                                      tzinfo=datetime.timezone.utc))

    @commands.group(case_insensitive=True, aliases=["sb"])
    async def skyblock(self, ctx):
        if ctx.invoked_subcommand is None:
            await ctx.reply(embed=self.bot.create_error_embed("Invalid format! "
                                                              "Please specify a subcommand. Valid "
                                                              "subcommands: `history`, `average`, `minimum`, `book`,"
                                                              "`tfm`"))

    @staticmethod
    async def do_profits_db_lookup(client, current_datetime, next_datetime, calculation):
        flips = await client.tfm.profits.find({"timestamp": {"$gt": current_datetime, "$lt": next_datetime}}).to_list(
            length=None)
        profit = sum([calculation(x) for x in flips])
        return current_datetime, profit

    @staticmethod
    async def do_flips_db_lookup(client, current_datetime, next_datetime, calculation):
        flips = await client.tfm.flips.find({"timestamp": {"$gt": current_datetime, "$lt": next_datetime}}).to_list(
            length=None)
        profit = sum([calculation(x) for x in flips])
        return current_datetime, profit

    async def produce_graph(self, ctx, name, y_label, calculation, db_lookup_func):
        data = self.cached_graphs[name]
        # If data is none (no cache), or it's from last hour, or it's greater than 2 hours old:
        if data is None or self.last_cached_time[name].hour != datetime.datetime.utcnow().hour or \
                ((datetime.datetime.utcnow() - self.last_cached_time[name]).total_seconds() / 3600) > 2:
            async with ctx.typing():
                client = self.bot.mongo.client
                # current_datetime = PROFITS_START_DATE if db_lookup_func == self.do_profits_db_lookup else \
                #     FLIPS_START_DATE
                tasks = []
                now = datetime.datetime.now()
                now = now.replace(tzinfo=datetime.timezone.utc)
                current_datetime = now - datetime.timedelta(days=30)
                while current_datetime < now:
                    next_datetime = current_datetime + datetime.timedelta(hours=1)
                    tasks.append(db_lookup_func(client, current_datetime, next_datetime,
                                                calculation))
                    current_datetime = next_datetime
                flip_data = await asyncio.gather(*tasks)
                with ProcessPoolExecutor() as pool:
                    data = await self.bot.loop.run_in_executor(pool, partial(tfm_graph, flip_data,
                                                                             y_label))
                self.cached_graphs[name] = data
                self.last_cached_time[name] = datetime.datetime.utcnow()
        file = BytesIO(data)
        file.seek(0)
        discord_file = discord.File(fp=file, filename="image.png")
        await ctx.reply(file=discord_file)

    @skyblock.group()
    async def tfm(self, ctx):
        if ctx.invoked_subcommand is not None:
            return

        def find_true_profit(x):
            if "sell_price" in x:
                return (x["sell_price"] * 0.99) - x["price"]
            # target is 80% of the price, take 2% for tax
            return (x["target"] / 0.82) - x["price"]

        await self.produce_graph(ctx, "tfm", "Average Profit (coins)", find_true_profit,
                                 self.do_profits_db_lookup)

    @tfm.command(name="help")
    async def tfm_help(self, ctx):
        await ctx.reply(embed=self.bot.create_completed_embed(
            "TFM Commands", "u!skyblock tfm <cost/purchases>\n"
                            "u!skyblock tfm flips [count]"))

    @tfm.command()
    async def cost(self, ctx):
        await self.produce_graph(ctx, "cost", "Average Cost (coins)", lambda x: x["price"],
                                 self.do_profits_db_lookup)

    @tfm.command()
    async def purchases(self, ctx):
        await self.produce_graph(ctx, "purchases", "Average Purchases", lambda x: 1,
                                 self.do_profits_db_lookup)

    @tfm.group()
    async def flips(self, ctx):
        if ctx.invoked_subcommand is not None:
            return
        await self.produce_graph(ctx, "flips_profit", "Average Theoretical Profit (coins)",
                                 lambda x: ((x["target"] + x["lowBin"]) // 2) - x["price"], self.do_flips_db_lookup)

    @flips.command()
    async def count(self, ctx):
        await self.produce_graph(ctx, "flips_count", "Average Theoretical Flips",
                                 lambda x: 1, self.do_flips_db_lookup)

    @skyblock.group(case_insensitive=True)
    async def book(self, ctx):
        if ctx.invoked_subcommand is None:
            await ctx.reply(embed=self.bot.create_error_embed("Invalid format! "
                                                              "Please specify a subcommand. Valid "
                                                              "subcommands: `history`, `average`, `minimum`"))

    async def all_auctions_average_data(self):
        pipeline = [{
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

    async def auctions_from_names(self, names, rarity=Rarity.ALL):
        pipeline = [
            {
                "$match": {
                    "item_name": {
                        "$in": names
                    },
                    "bin": True,
                    "sold": True,
                    "tier": rarity.name if rarity != Rarity.ALL else {"$exists": True},
                    "count": 1
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

    async def all_auctions_determine(self):
        minimum_prices = []
        average_prices = []
        maximum_prices = []
        for auction in await self.all_auctions_average_data():
            minimum_prices.append((auction["_id"], auction["minimum"]))
            average_prices.append((auction["_id"], auction["average"]))
            maximum_prices.append((auction["_id"], auction["maximum"]))
        minimum_prices.sort(key=lambda x: x[0])
        average_prices.sort(key=lambda x: x[0])
        maximum_prices.sort(key=lambda x: x[0])
        return minimum_prices, average_prices, maximum_prices

    async def get_item_from_name(self, item_names, rarity=Rarity.ALL):
        minimum_prices = []
        average_prices = []
        maximum_prices = []
        for auction in await self.auctions_from_names(item_names, rarity):
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
        print(ctx)
        print(type(ctx))
        print(self)
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
    async def book_minimum(self, ctx, *, query):
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
                    "$text": {"$search": f"{query}"},
                    "sold": True
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
                      "sold": True,
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
            if query.lower() == "all":
                minimum_prices, average_prices, maximum_prices = await self.all_auctions_determine()
            else:
                valid_names, rarity = await self.ask_name(ctx, query)
                minimum_prices, average_prices, maximum_prices = await self.get_item_from_name(valid_names, rarity)
            if len(maximum_prices) == 0:
                await ctx.reply(embed=self.bot.create_error_embed("No auctions could be found."))
                return
            with ProcessPoolExecutor() as pool:
                data = await self.bot.loop.run_in_executor(pool, partial(plot_multiple,
                                                                         title=f"Historical prices for {query}",
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
            if query.lower() == "all":
                minimum_prices, average_prices, maximum_prices = await self.all_auctions_determine()
            else:
                valid_names, rarity = await self.ask_name(ctx, query)
                minimum_prices, average_prices, maximum_prices = await self.get_item_from_name(valid_names, rarity)
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

    async def ask_rarity(self, ctx):
        await ctx.reply(
            embed=self.bot.create_completed_embed("Rarity",
                                                  "Respond with the rarity you would like to search for.\n\n" +
                                                  "\n ".join([f"{i} - {x}" for i, x in
                                                              [(x.value, x.name) for x in Rarity]])))
        rarity_index = await self.bot.ask_question(ctx, None)
        try:
            rarity_index = int(rarity_index)
        except ValueError:
            await ctx.reply(embed=self.bot.create_error_embed("Invalid index! Please enter a valid number. "
                                                              "Returning to rarity input."))
            return await self.ask_rarity(ctx)
        if rarity_index < 0 or rarity_index > len(Rarity) - 1:
            await ctx.reply(embed=self.bot.create_error_embed("That's not a valid rarity! Returning to rarity input."))
            return await self.ask_rarity(ctx)

        return Rarity(rarity_index)

    async def ask_name(self, ctx, query):
        all_names = await self.skyblock_db.auctions.distinct("item_name")
        valid_names = [x for x in all_names if query.lower() in x.lower()]
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
        rarity = await self.ask_rarity(ctx)
        return valid_names, rarity

    @skyblock.command()
    async def minimum(self, ctx, *, query):
        async with ctx.typing():
            if query.lower() == "all":
                minimum_prices, average_prices, maximum_prices = await self.all_auctions_determine()
            else:
                valid_names, rarity = await self.ask_name(ctx, query)
                minimum_prices, average_prices, maximum_prices = await self.get_item_from_name(valid_names, rarity)
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

    async def get_sell_price(self, names, rarity):
        pipeline = [
            {
                "$match": {
                    "item_name": {
                        "$in": names
                    },
                    "bin": True,
                    "sold": True,
                    "tier": rarity.name if rarity != Rarity.ALL else {"$exists": True},
                    "count": 1
                }
            },
            {
                "$unwind": "$updates"
            },
            {
                "$group": {
                    "_id": None,
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
        data = await self.skyblock_db.auctions.aggregate(pipeline).to_list(length=None)
        data = data[0]
        return data["minimum"], round(data["average"], 2), data["maximum"]

    @skyblock.command(aliases=["sp"])
    async def sell_price(self, ctx, *, query):
        async with ctx.typing():
            valid_names, rarity = await self.ask_name(ctx, query)
            try:
                minimum, average, maximum = await self.get_sell_price(valid_names, rarity)
            except (KeyError, IndexError):
                await ctx.reply("That item appears to have never sold!")
                return
            await ctx.reply(embed=self.bot.create_completed_embed(f"{query}", f"Minimum Sell Price: {minimum:,} coins\n"
                                                                              f"Average Sell Price: {average:,} coins\n"
                                                                              f"Maximum Sell Price: {maximum:,} coins"))


def setup(bot):
    cog = Skyblock(bot)
    bot.add_cog(cog)
