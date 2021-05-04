import asyncio
import re
import concurrent.futures

import discord
from discord.ext import commands, tasks
from io import BytesIO
from typing import Optional, Union
from functools import partial

from main import UtilsBot
from src.checks.user_check import is_owner
from src.helpers.tiktok_helper import get_video, get_user
from src.helpers.storage_helper import DataHelper
from src.checks.guild_check import monkey_check
from src.checks.message_check import check_trusted_reaction
from src.checks.role_check import is_staff
from src.storage import config


class Monkey(commands.Cog):
    def __init__(self, bot: UtilsBot):
        self.bot: UtilsBot = bot
        self.previous_counting_number = None
        self.data = DataHelper()
        self.tiktok_db = self.bot.mongo.client.tiktok
        self.send_tiktok_message.start()
        self.update_followers.start()

    @tasks.loop(seconds=30, count=None)
    async def send_tiktok_message(self):
        tiktok_channels = self.tiktok_db.notifications
        async for channel in tiktok_channels.find():
            username = channel.get("username")
            channel_id = channel.get("channel_id")
            last_ids = channel.get("last_ids", [])
            text = channel.get("text", None)
            updates_channel = self.bot.get_channel(channel_id)
            if updates_channel is None:
                continue
            with concurrent.futures.ProcessPoolExecutor() as pool:
                last_video, image = await asyncio.get_event_loop().run_in_executor(pool, partial(get_video, username))
            video_id = last_video.get('video', {}).get('id')
            if video_id in last_ids:
                continue
            if len(last_ids) > 4:
                last_ids.pop(0)
            last_ids.append(video_id)
            embed = discord.Embed()
            image = BytesIO(image)
            file = discord.File(fp=image, filename="image.png")
            embed.set_image(url="attachment://image.png")
            link = f"https://www.tiktok.com/@{last_video.get('author', {}).get('uniqueId', '')}/video/{video_id}"
            embed.title = last_video.get('desc', '<no description>')
            embed.description = f"{last_video.get('author', {}).get('nickname', '')} just uploaded a new video!"
            embed.url = link
            embed.set_author(name=f"@{last_video.get('author', {}).get('uniqueId', '')}",
                             icon_url=last_video.get('author', {}).get('avatarLarger', ''))
            if text is None:
                await updates_channel.send(embed=embed, file=file)
            else:
                await updates_channel.send(embed=embed, file=file, content=text)
            await self.tiktok_db.notifications.update_one({"channel_id": channel_id, "username": username},
                                                          {"$set": {"last_ids": last_ids}})

    @tasks.loop(seconds=600, count=None)
    async def update_followers(self):
        follower_channels = self.tiktok_db.followers
        async for channel in follower_channels.find():
            username = channel.get("username")
            update_channel_id = channel.get("channel_id")
            discord_channel = self.bot.get_channel(update_channel_id)
            if discord_channel is None:
                continue
            with concurrent.futures.ProcessPoolExecutor() as pool:
                user = await asyncio.get_event_loop().run_in_executor(pool, partial(get_user, username))
            followers = user.get("userInfo").get("stats").get("followerCount", "Unknown")
            await discord_channel.edit(name=f"Followers: {followers:,}")

    @commands.command()
    @is_owner()
    async def set_notifications(self, ctx, username: str, channel: Optional[discord.TextChannel],
                                optional_text: str = None):
        overwrites = {ctx.guild.default_role: discord.PermissionOverwrite(read_messages=True, send_messages=False),
                      ctx.guild.me: discord.PermissionOverwrite(read_messages=True, send_messages=True)}
        if channel is None:
            channel = await ctx.guild.create_text_channel("tiktok-notifications", overwrites=overwrites)
        if optional_text == "":
            optional_text = None
        channel_document = {"channel_id": channel.id, "username": username, "text": optional_text}
        await self.bot.mongo.force_insert(self.tiktok_db.notifications, channel_document)
        await ctx.reply("Set notifications channel as {}".format(channel.mention))

    @commands.command()
    @is_owner()
    async def set_followers(self, ctx, username: str, channel: Optional[discord.VoiceChannel]):
        overwrites = {ctx.guild.default_role: discord.PermissionOverwrite(view_channel=True, connect=False),
                      ctx.guild.me: discord.PermissionOverwrite(view_channel=True, connect=True)}
        if channel is None:
            channel = await ctx.guild.create_voice_channel("Followers: Pending", overwrites=overwrites)
        channel_document = {"channel_id": channel.id, "username": username}
        await self.bot.mongo.force_insert(self.tiktok_db.followers, channel_document)
        await ctx.reply("Set followers channel as {}".format(channel.mention))

    @commands.command()
    @is_owner()
    async def reset_notifications(self, ctx, channel: discord.TextChannel):
        await self.tiktok_db.notifications.delete_many({"channel_id": channel.id})
        await ctx.reply("Removed notification channel.")

    @commands.command()
    @is_owner()
    async def reset_followers(self, ctx, channel: discord.VoiceChannel):
        await self.tiktok_db.followers.delete_many({"channel_id": channel.id})
        await ctx.reply("Removed followers channel.")

    @commands.command()
    @monkey_check()
    @is_staff()
    async def trust(self, ctx, member: discord.Member):
        trusted_role = ctx.guild.get_role(config.trusted_role_id)
        trusted_spiel = """A moderator from ahhh monkey has offered you the Trusted role, which allows you to send 
        pictures and links. React to this to accept the rules and gain Trusted status. \n
As a member with the Trusted role, I agree that all images and links I send will be in conformance with Discord 
Community Guidelines and the server rules. I acknowledge that my trusted status may be taken away at any time if I 
break these rules. \n
This invite expires in 5 minutes. You may ask for a new one if it expires."""
        sent = await member.send(content=trusted_spiel)
        await sent.add_reaction('👍')
        try:
            await self.bot.wait_for("reaction_add", timeout=300.0, check=check_trusted_reaction(member, sent.id))
            await member.add_roles(trusted_role)
            await member.send("You have been trusted!")
        except asyncio.TimeoutError:
            await member.send(content="Timed out.")

    @commands.Cog.listener()
    @monkey_check()
    async def on_message(self, message: discord.Message):
        chill_peeps = message.guild.get_role(725895768703238255)
        if isinstance(message.author, discord.Member) and \
                len([x for x in message.author.roles if x != message.guild.default_role]) == 0:
            if chill_peeps is None:
                return
            await message.author.add_roles(chill_peeps)
        if message.author.id == self.bot.user.id and message.channel.id == config.counting_channel_id:
            await asyncio.sleep(10)
            try:
                await message.delete()
            except discord.errors.NotFound:
                pass
            return
        if message.author.id != self.bot.user.id and message.channel.id == config.staff_polls_channel_id:
            await message.delete(delay=1)
            return
        if message.channel.id == config.counting_channel_id:
            count = 15
            while True:
                try:
                    previous_messages = [x for x in await message.channel.history(limit=count).flatten()
                                         if not x.author.id == self.bot.user.id]
                    previous_message = previous_messages[1]
                    break
                except IndexError:
                    count += 10
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


def setup(bot):
    cog = Monkey(bot)
    bot.add_cog(cog)
