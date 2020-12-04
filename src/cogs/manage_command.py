from discord.ext import commands

from main import UtilsBot
from src.checks.role_check import is_high_staff


class CommandManager(commands.Cog):
    def __init__(self, bot: UtilsBot):
        self.bot = bot

    @commands.command()
    @is_high_staff()
    async def disable(self, ctx, command_name):
        command: commands.Command = self.bot.get_command(command_name)
        if command is None:
            await ctx.send(embed=self.bot.create_error_embed("Couldn't find a command with that name."))
            return
        if not command.enabled:
            await ctx.send(embed=self.bot.create_error_embed("Command already disabled."))
            return
        command.update(enabled=False)
        await ctx.send(embed=self.bot.create_completed_embed("Disabled.", "Command {} disabled!".format(command_name)))

    @commands.command()
    @is_high_staff()
    async def enable(self, ctx, command_name):
        command: commands.Command = self.bot.get_command(command_name)
        if command is None:
            await ctx.send(embed=self.bot.create_error_embed("Couldn't find a command with that name."))
        if command.enabled:
            await ctx.send(embed=self.bot.create_error_embed("Command already enabled."))
            return
        command.update(enabled=True)
        await ctx.send(embed=self.bot.create_completed_embed("Enabled.", "Command {} enabled!".format(command_name)))
        await command.callback(ctx)


def setup(bot):
    cog = CommandManager(bot)
    bot.add_cog(cog)
