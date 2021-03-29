import discord
import json


def message_to_json(message: discord.Message):
    message_dict = {"channel": channel_to_json(message.channel), "author": user_to_json(message.author),
                    "id": message.id, "content": message.content, "created_at": message.created_at.isoformat()}
    if len(message.embeds) > 0:
        embed = message.embeds[0]
        message_dict["embed_json"] = json.dumps(embed.to_dict())
    return message_dict


def channel_to_json(channel: discord.TextChannel):
    channel_dict = {"id": channel.id, "name": channel.name, "guild": guild_to_json(channel.guild)}
    return channel_dict


def guild_to_json(guild: discord.Guild):
    guild_dict = {"id": guild.id, "name": guild.name}
    return guild_dict


def user_to_json(user: discord.User):
    user_dict = {"id": user.id, "name": user.name, "bot": user.bot}
    return user_dict


def role_to_json(role: discord.Role):
    role_dict = {"id": role.id, "name": role.name, "permissions": role.permissions.value, "colour": role.colour.value,
                 "mentionable": role.mentionable, "hoist": role.hoist}
    return role_dict


def member_to_json(member: discord.Member):
    member_dict = {"user": user_to_json(member), "nick": member.nick, "joined_at": member.joined_at.isoformat(),
                   "guild": guild_to_json(member.guild)}
    roles = []
    for role in member.roles:
        roles.append(role_to_json(role))
    member_dict["roles"] = roles
    return member_dict
