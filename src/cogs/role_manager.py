import discord
from discord.ext import commands, tasks

from typing import Optional
from src.checks.role_check import is_staff
from main import UtilsBot


class RoleManager(commands.Cog):
    def __init__(self, bot: UtilsBot):
        self.bot = bot
        self.rejoin_guilds = self.bot.mongo.discord_db.rejoin_guilds
        self.rejoin_logs = self.bot.mongo.discord_db.rejoin_logs

    @commands.command()
    @is_staff()
    async def set_role_reapply(self, ctx, max_role: Optional[discord.Role]):
        guild_document = {"_id": ctx.guild.id, "max_role": max_role.id}
        await self.bot.mongo.force_insert(self.rejoin_guilds, guild_document)
        if max_role is None:
            await ctx.reply(embed=self.bot.create_completed_embed("Guild Added", "The guild has been set-up for role "
                                                                                 "re-application."))
        else:
            await ctx.reply(embed=self.bot.create_completed_embed("Guild Added", "The guild has been set-up for role "
                                                                                 "re-application for all roles below "
                                                                                 f"{max_role.mention}"))

    @commands.command()
    @is_staff()
    async def unset_role_reapply(self, ctx):
        await self.rejoin_guilds.delete_one({"_id": ctx.guild.id})
        await ctx.reply(embed=self.bot.create_completed_embed("Guild Added", "The guild has been removed from role "
                                                                             "re-application."))

    @commands.Cog.listener()
    async def on_member_remove(self, member):
        member_role_document = {"_id": {"user_id": member.id, "guild_id": member.guild.id},
                                "roles": [role.id for role in member.roles if role != member.guild.default_role]}
        await self.bot.mongo.force_insert(self.rejoin_logs, member_role_document)

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        guild_id = member.guild.id
        guild_doc = await self.rejoin_guilds.find_one({"_id": guild_id})
        if guild_doc is None:
            return
        max_role_id = guild_doc.get("max_role", None)
        if max_role_id is None:
            check = lambda x: True
        else:
            max_role = member.guild.get_role(max_role_id)
            check = lambda x: x < max_role
        member_role_document = await self.rejoin_logs.find_one({"_id": {"user_id": member.id,
                                                                        "guild_id": member.guild.id}})
        if member_role_document is None:
            return
        valid_roles = []
        for role_id in member_role_document.get("roles"):
            role = member.guild.get_role(role_id)
            if role is None or role == member.guild.default_role:
                continue
            if check(role):
                valid_roles.append(role)
        try:
            await member.add_roles(*valid_roles)
        except discord.errors.Forbidden:
            for role in valid_roles:
                try:
                    await member.add_roles(role)
                except discord.errors.Forbidden:
                    print(f"I am forbidden from adding role {role.name} in guild {member.guild.name} to {member.name}")


def setup(bot):
    cog = RoleManager(bot)
    bot.add_cog(cog)
