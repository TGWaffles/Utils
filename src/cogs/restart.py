import asyncio
import discord
from subprocess import Popen, check_output

from discord.ext import commands

from src.checks.user_check import is_owner
from src.checks.custom_check import restart_check
from src.helpers.storage_helper import DataHelper
from src.storage import config
from main import UtilsBot


class Restart(commands.Cog):
    def __init__(self, bot: UtilsBot):
        self.bot: UtilsBot = bot

    @commands.command(pass_context=True)
    @is_owner()
    async def update(self, ctx: commands.Context):
        reply_message = await ctx.reply(embed=self.bot.create_processing_embed("Updating", "Downloading update..."))
        git_pull = Popen(["git", "pull"])
        waited = 0
        while git_pull.poll() is None:
            await asyncio.sleep(0.2)
            waited += 0.2
            if waited > 5.0:
                await reply_message.edit(embed=self.bot.create_error_embed("Update download failed."))
                return
        await self.bot.database_handler.update()
        await reply_message.edit(embed=self.bot.create_processing_embed("Restarting", "Update download completed! "
                                                                                      "Restarting database..."))
        self.bot.completed_restart_write(ctx.channel.id, reply_message.id, "Update Complete!",
                                         "Updated and Restarted successfully!")
        await self.bot.database_handler.restart_db_server()
        await self.wait_on_events(reply_message)
        self.bot.restart()
        await reply_message.edit(embed=self.bot.create_error_embed("Apparently the restart failed. What?"))

    @commands.command(pass_context=True)
    @restart_check()
    async def restart(self, ctx: commands.Context):
        reply_message = await ctx.reply(embed=self.bot.create_processing_embed("Restarting", "Beginning restart..."))
        await self.wait_on_events(reply_message)

        self.bot.completed_restart_write(ctx.channel.id, reply_message.id, "Restart Complete!",
                                         "Restarted successfully!")
        self.bot.restart()
        await reply_message.edit(embed=self.bot.create_error_embed("Apparently the restart failed. What?"))

    async def wait_on_events(self, message):
        await message.edit(embed=self.bot.create_processing_embed("Waiting on restart tasks...",
                                                                  "Waiting on restart tasks to finish up then "
                                                                  "restarting..."))
        self.bot.restart_event.set()
        await asyncio.sleep(0.5)
        while self.bot.restart_waiters != 0:
            await asyncio.sleep(0.05)

    @commands.command()
    @is_owner()
    async def restart_perms(self, ctx, member: discord.Member):
        data = DataHelper()
        restart_users = data.get("restart_perms", [])
        if str(member.id) in restart_users:
            restart_users.remove(str(member.id))
            await ctx.reply(embed=self.bot.create_completed_embed("Perms Removed!", "Taken {}'s permissions to "
                                                                                    "restart the bot.".format(
                member.mention)))
        else:
            restart_users.append(str(member.id))
            await ctx.reply(embed=self.bot.create_completed_embed("Perms Granted!",
                                                                  "Given {} permission to restart the bot.".format(
                                                                      member.mention)))
        data["restart_perms"] = restart_users

    @commands.command()
    async def changelog(self, ctx):
        last_commit_message = check_output(["git", "log", "-1", "--pretty=%s"]).decode("utf-8").strip()
        version_number = config.version_number
        embed = discord.Embed(title=f"Version {version_number}", colour=discord.Colour.purple())
        embed.add_field(name="Most Recent Update", value=last_commit_message)
        embed.set_footer(text="Update courtesy of Thomas_Waffles#0001")
        await ctx.reply(embed=embed)


def setup(bot):
    cog = Restart(bot)
    bot.add_cog(cog)
