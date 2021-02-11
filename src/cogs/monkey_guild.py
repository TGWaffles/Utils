import re
import discord
import random

from discord.ext import commands

from main import UtilsBot
from src.storage import config
from src.checks.guild_check import sparky_check
from src.helpers.storage_helper import DataHelper


class Monkey(commands.Cog):
    def __init__(self, bot: UtilsBot):
        self.bot: UtilsBot = bot
        # self.july = datetime.datetime(2020, 7, 1, tzinfo=datetime.timezone.utc)
        self.previous_counting_number = None
        self.data = DataHelper()

    # def is_og(self, member: discord.Member):
    #     first_join_date = member.joined_at
    #     # noinspection SpellCheckingInspection
    #     first_join_date = first_join_date.replace(tzinfo=datetime.timezone.utc)
    #     return first_join_date < self.july
    #
    # @commands.command(pass_context=True)
    # @monkey_check()
    # async def check_og(self, ctx, member: discord.Member = None):
    #     if member is None:
    #         member = ctx.message.author
    #     is_og = self.is_og(member)
    #     message_time = None
    #     data = DataHelper()
    #     if str(member.id) in data.get("og_messages", {}).keys():
    #         is_og = True
    #         message_time = datetime.datetime.utcfromtimestamp(data.get("og_messages", {}).get(str(member.id), 0))
    #     embed = discord.Embed(title="OG Check")
    #     embed.set_author(name=member.name, icon_url=member.avatar_url)
    #     embed.description = "{} Member {} OG".format(("❌", "✅")[int(is_og)], ("is not", "is")[int(is_og)])
    #     embed.colour = (discord.Colour.red(), discord.Colour.green())[int(is_og)]
    #     embed.timestamp = member.joined_at
    #     if message_time is not None:
    #         embed.timestamp = message_time
    #         embed.add_field(name="First Message", value=message_time.strftime("%Y-%m-%d %H:%M"))
    #     if self.bot.latest_joins == {}:
    #         await self.bot.get_latest_joins()
    #     members = self.bot.latest_joins[ctx.guild.id]
    #     members = [user.id for user in members]
    #     embed.add_field(name="Position", value="#{}".format(str(members.index(member.id) + 1)))
    #     await ctx.reply(embed=embed)
    #
    # @commands.command(pass_context=True)
    # @is_owner()
    # @monkey_check()
    # async def all_ogs(self, ctx):
    #     message_member_ids = {}
    #     start_embed = discord.Embed(title="Doing all OGs.", description="I will now start to process all messages "
    #                                                                     "until the 1st of July.",
    #                                 colour=discord.Colour.orange())
    #     processing_message = await ctx.reply(embed=start_embed)
    #     last_edit = datetime.datetime.now()
    #     for channel in ctx.guild.text_channels:
    #         async for message in channel.history(limit=None, before=self.july.replace(tzinfo=None), oldest_first=True):
    #             author = message.author
    #             if (datetime.datetime.now() - last_edit).total_seconds() > 1:
    #                 embed = discord.Embed(title="Processing messages",
    #                                       description="Last Message text: {}, from {}, in {}".format(
    #                                           message.clean_content, message.created_at.strftime("%Y-%m-%d %H:%M"),
    #                                           channel.mention), colour=discord.Colour.orange())
    #                 embed.set_author(name=author.name, icon_url=author.avatar_url)
    #                 embed.timestamp = message.created_at
    #                 await processing_message.edit(embed=embed)
    #                 last_edit = datetime.datetime.now()
    #             if str(author.id) not in message_member_ids.keys():
    #                 join_date = message.created_at.replace(tzinfo=datetime.timezone.utc)
    #                 message_member_ids[str(author.id)] = join_date.timestamp()
    #     messages_done = discord.Embed(title="Finished Messages.", description="Finished messages. I will now start to "
    #                                                                           "apply the OG role to all deserving "
    #                                                                           "users.", colour=discord.Colour.orange())
    #     await processing_message.edit(embed=messages_done)
    #     last_edit = datetime.datetime.now()
    #     og_role = ctx.guild.get_role(795873287628128306)
    #     members_processed = 0
    #     async for member in ctx.guild.fetch_members(limit=None):
    #         has_message = str(member.id) in message_member_ids.keys()
    #         if has_message:
    #             message_creation_date = datetime.datetime.fromtimestamp(message_member_ids[str(member.id)],
    #                                                                     datetime.timezone.utc)
    #             message_creation_message = message_creation_date.strftime("%Y-%m-%d %H:%M")
    #             join_time = min(message_creation_date,
    #                             member.joined_at.replace(tzinfo=datetime.timezone.utc))
    #         else:
    #             message_creation_message = "No"
    #             join_time = member.joined_at.replace(tzinfo=datetime.timezone.utc)
    #         is_og = join_time < self.july
    #         if (datetime.datetime.now() - last_edit).total_seconds() > 1:
    #             embed = discord.Embed(title="Processing Members...",
    #                                   description="Last Member: {}. "
    #                                               "Joined at: {}. "
    #                                               "Has previous message: {}."
    #                                               "Is OG: {}".format(member.name,
    #                                                                  member.joined_at.strftime("%Y-%m-%d %H:%M"),
    #                                                                  message_creation_message,
    #                                                                  is_og))
    #             embed.set_author(name=member.name, icon_url=member.avatar_url)
    #             embed.timestamp = join_time.replace(tzinfo=None)
    #             await processing_message.edit(embed=embed)
    #             last_edit = datetime.datetime.now()
    #         if is_og:
    #             try:
    #                 await member.add_roles(og_role)
    #             except Exception as e:
    #                 print(e)
    #             members_processed += 1
    #     embed = self.bot.create_completed_embed("Completed OG addition", "Successfully added all OGs!")
    #     await processing_message.edit(embed=embed)
    #     data = DataHelper()
    #     data["og_messages"] = message_member_ids

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.id == self.bot.user.id:
            return
        if message.channel.id == config.counting_channel_id:
            previous_messages = [x for x in await message.channel.history(limit=15).flatten()
                                 if not x.author.id == self.bot.user.id]
            previous_message = previous_messages[1]
            if previous_message.author.id == message.author.id:
                await message.reply(embed=self.bot.create_error_embed("You can't send two numbers in a row!"),
                                    delete_after=7)
                await message.delete()
                return
            if self.previous_counting_number is None:
                try:
                    previous_number = int(re.findall(r"\d+", previous_message.clean_content)[0])
                except (IndexError, ValueError):
                    await message.reply(embed=self.bot.create_error_embed("Failed to detect previous number. "
                                                                          "Deleting both."), delete_after=7)
                    await message.delete()
                    await previous_message.delete()
                    return
            else:
                previous_number = self.previous_counting_number
            numbers_in_message = [int(x) for x in re.findall(r"\d+", message.clean_content)]
            if len(numbers_in_message) == 0:
                await message.reply(embed=self.bot.create_error_embed("That doesn't appear to have been a number."),
                                    delete_after=5)
                await message.delete()
                return
            elif len(numbers_in_message) > 1 and previous_number + 2 in numbers_in_message:
                await message.reply(embed=self.bot.create_error_embed("Only one number per message, please!"),
                                    delete_after=5)
                await message.delete()
                return
            if previous_number + 1 not in numbers_in_message:
                await message.reply(embed=self.bot.create_error_embed("{}'s not the next number, {} "
                                                                      "(I'm looking for {})".format(
                    numbers_in_message[0], message.author.mention,
                    previous_number + 1)), delete_after=7)
                await message.delete()
                return
            else:
                self.previous_counting_number = previous_number + 1

    @commands.Cog.listener()
    async def on_message_edit(self, before, after):
        if after.channel.id != config.counting_channel_id or before.author.id == self.bot.user.id:
            return
        previous_messages = [x for x in await before.channel.history(limit=15, before=before).flatten()
                             if x.author.id != self.bot.user.id and x.author.id != before.author.id]
        previous_message = previous_messages[1]
        if ((await before.channel.history(limit=1).flatten())[0] == after and
                self.previous_counting_number is not None):
            previous_number = self.previous_counting_number - 1
        else:
            previous_number = int(re.findall(r"\d+", previous_message.clean_content)[0])
        searching_for_number = previous_number + 1
        numbers_in_message = [int(x) for x in re.findall(r"\d+", before.clean_content)]
        try:
            closest_number = numbers_in_message[min(range(len(numbers_in_message)),
                                                    key=lambda i: abs(numbers_in_message[i] - searching_for_number))]
            numbers_in_edited_message = [int(x) for x in re.findall(r"\d+", after.clean_content)]
            assert closest_number in numbers_in_edited_message
        except (ValueError, IndexError, AssertionError):
            if (await before.channel.history(limit=1).flatten())[0] == after:
                self.previous_counting_number = previous_number
            await after.reply(embed=self.bot.create_error_embed("Message was edited. \n\n"
                                                                "You removed the number that kept this message valid, "
                                                                "so it will now be deleted."), delete_after=7)
            await after.delete()

    @commands.command()
    @sparky_check()
    async def kick_roulette(self, ctx):
        random_person = random.choice([member for member in ctx.channel.members if not member.bot and
                                       not member.id == config.lexi_id and not member == ctx.guild.owner])
        channel = ctx.guild.text_channels[0]
        role_ids = []
        for role in random_person.roles:
            role_ids.append(role.id)
        all_members = self.data.get("reapply_roles", {})
        all_members[str(random_person.id)] = role_ids
        self.data["reapply_roles"] = all_members
        invite = await channel.create_invite(max_uses=1, reason="Kick Roulette save")
        await ctx.reply("Your kick roulette was: {}".format(random_person.mention))
        await random_person.send(content="You were chosen for kick roulette. The invite is: {}".format(invite.url))
        await random_person.kick(reason="Kick Roulette.")

    @commands.Cog.listener()
    async def on_member_join(self, member):
        if member.guild.id == config.sparky_guild_id:
            all_members = self.data.get("reapply_roles", {})
            if str(member.id) in all_members:
                role_list = []
                for role in all_members[str(member.id)]:
                    role = member.guild.get_role(int(role))
                    if role is not None:
                        try:
                            await member.add_roles(role)
                        except:
                            print(role)
                            print(role.id)


def setup(bot):
    cog = Monkey(bot)
    bot.add_cog(cog)
