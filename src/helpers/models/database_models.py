import discord
import json
from threading import Lock
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship, Session
from sqlalchemy import Column, BigInteger, String, Boolean, ForeignKey, ForeignKeyConstraint, DateTime

Base = declarative_base()
channel_lock = Lock()
user_lock = Lock()
member_lock = Lock()
member_roles_lock = Lock()
guild_lock = Lock()
role_lock = Lock()
message_lock = Lock()
edit_lock = Lock()


class Guild(Base):
    __tablename__ = 'guild'
    id = Column(BigInteger, primary_key=True)
    name = Column(String(100))
    removed = Column(Boolean)

    @classmethod
    def from_discord(cls, session: Session, guild: discord.Guild):
        with session.no_autoflush, guild_lock:
            guild_object = session.query(Guild).filter_by(id=guild.id).first()
            if guild_object is None:
                guild_object = Guild(id=guild.id)
                session.add(guild_object)
        guild_object.name = guild.name
        guild_object.removed = False
        session.commit()
        return guild_object

    @classmethod
    def update_from_discord(cls, session: Session, guild: discord.Guild):
        guild_object = cls.from_discord(session, guild)
        for channel in guild.text_channels:
            text_channel_object = Channel.from_discord_and_guild(session, channel, guild_object)
            if text_channel_object not in guild_object.text_channels:
                guild_object.text_channels.append(text_channel_object)
        for member in guild.members:
            member_to_guild = Member.update_member(session, member)
            guild_object.members.append(member_to_guild)
        session.commit()
        return guild_object

    @classmethod
    def delete(cls, session, guild):
        with session.no_autoflush, guild_lock:
            guild_object = session.query(Guild).filter_by(id=guild.id).first()
            if guild_object is None:
                return False
        guild_object.removed = True
        session.commit()
        return True


class Role(Base):
    __tablename__ = "role"
    id = Column(BigInteger, primary_key=True)
    guild_id = Column(BigInteger, ForeignKey("guild.id"), primary_key=True)
    guild = relationship("Guild")
    role_permissions = Column(BigInteger)
    name = Column(String(100))
    colour = Column(BigInteger)
    mentionable = Column(Boolean)
    hoisted = Column(Boolean)

    @classmethod
    def from_discord_and_guild(cls, session, role: discord.Role, guild_object: Guild):
        with session.no_autoflush, role_lock:
            role_object = session.query(Role).filter_by(id=role.id).first()
            if role_object is None:
                role_object = Role(id=role.id, guild=guild_object)
                session.add(role_object)
        role_object.role_permissions = role.permissions.value
        role_object.name = role.name
        role_object.colour = role.colour.value
        role_object.mentionable = role.mentionable
        role_object.hoisted = role.hoist
        session.commit()
        return role_object

    @classmethod
    def from_discord(cls, session, role: discord.Role):
        guild_object = Guild.from_discord(session, role.guild)
        return cls.from_discord_and_guild(session, role, guild_object)

    @classmethod
    def delete(cls, session, role: discord.Role):
        with session.no_autoflush, role_lock:
            role_object = session.query(Role).filter_by(id=role.id).first()
            if role_object is None:
                return False
        session.delete(role_object)


class Member(Base):
    __tablename__ = "member"
    user_id = Column(BigInteger, ForeignKey("user.id"), primary_key=True)
    user = relationship("User", backref="members")
    guild_id = Column(BigInteger, ForeignKey("guild.id"), primary_key=True)
    guild = relationship("Guild", backref="members")
    nick = Column(String(32))
    roles = relationship("MemberToRole", back_populates="member", cascade="save-update, merge, delete, delete-orphan")
    joined_at = Column(DateTime)

    @classmethod
    def update_member(cls, session, discord_member: discord.Member):
        if not isinstance(discord_member, discord.Member):
            return None
        with session.no_autoflush, member_lock:
            member_to_guild = session.query(Member).get((discord_member.id, discord_member.guild.id))
            if member_to_guild is None:
                member_to_guild = Member(user_id=discord_member.id,
                                         guild_id=discord_member.guild.id)
                # noinspection PyTypeChecker
                member_to_guild.user = User.from_discord(session, discord_member)
                session.add(member_to_guild)
                session.commit()
        member_to_guild.nick = discord_member.nick
        member_to_guild.joined_at = discord_member.joined_at
        member_to_roles: list = member_to_guild.roles.copy()
        known_role_ids = [role.role_id for role in member_to_roles]
        current_role_ids = [role.id for role in discord_member.roles]
        for known_role in member_to_roles:
            if known_role.role_id not in current_role_ids:
                member_to_guild.roles.remove(known_role)
                session.delete(known_role)
        for current_role in discord_member.roles:
            if current_role.id not in known_role_ids:
                role = Role.from_discord(session, current_role)
                member_to_guild.roles.append(MemberToRole.from_member_and_role(session, member_to_guild, role))
        session.commit()
        return member_to_guild

    @classmethod
    def delete_member(cls, session, discord_member: discord.Member):
        with session.no_autoflush, member_lock:
            member_to_guild = session.query(Member).filter_by(user_id=discord_member.id,
                                                              guild_id=discord_member.guild.id).first()
            if member_to_guild is None:
                return False
        session.delete(member_to_guild)
        session.commit()
        return True


class MemberToRole(Base):
    __tablename__ = "member_roles"
    role_id = Column(BigInteger, ForeignKey("role.id"), primary_key=True)
    role = relationship("Role", backref="members")
    user_id = Column(BigInteger, ForeignKey("user.id"), primary_key=True)
    guild_id = Column(BigInteger)
    __table_args__ = (ForeignKeyConstraint((user_id, guild_id),
                                           [Member.user_id, Member.guild_id]), {})
    member = relationship("Member", back_populates="roles")

    @classmethod
    def from_member_and_role(cls, session, member: Member, role: Role):
        with session.no_autoflush, member_roles_lock:
            role_to_member = session.query(MemberToRole).filter_by(role_id=role.id, user_id=member.user_id,
                                                                   guild_id=member.guild_id).first()
            if role_to_member is None:
                role_to_member = MemberToRole()
        role_to_member.guild_id = member.guild_id
        role_to_member.user_id = member.user_id
        role_to_member.role = role
        return role_to_member


class User(Base):
    __tablename__ = 'user'
    id = Column(BigInteger, primary_key=True)
    name = Column(String(32))
    bot = Column(Boolean)

    @classmethod
    def from_discord(cls, session, user: discord.User):
        with session.no_autoflush, user_lock:
            user_object = session.query(User).filter_by(id=user.id).first()
            if user_object is None:
                user_object = User(id=user.id)
                session.add(user_object)
        user_object.name = user.name
        user_object.bot = user.bot
        session.commit()
        return user_object


class Channel(Base):
    __tablename__ = "channel"
    id = Column(BigInteger, primary_key=True)
    name = Column(String(100))
    guild_id = Column(BigInteger, ForeignKey("guild.id"))
    guild = relationship("Guild", backref="text_channels")

    @classmethod
    def from_discord_and_guild(cls, session, text_channel: discord.TextChannel, guild: Guild):
        with session.no_autoflush, channel_lock:
            text_channel_object = session.query(Channel).filter_by(id=text_channel.id).first()
            if text_channel_object is None:
                text_channel_object = Channel(id=text_channel.id)
                session.add(text_channel_object)
                session.commit()
        text_channel_object.name = text_channel.name
        text_channel_object.guild = guild
        session.commit()
        return text_channel_object

    @classmethod
    def from_discord(cls, session, text_channel: discord.TextChannel):
        guild_object = Guild.from_discord(session, text_channel.guild)
        return cls.from_discord_and_guild(session, text_channel, guild_object)

    @classmethod
    def delete_channel(cls, session, channel):
        with session.no_autoflush, channel_lock:
            text_channel_object = session.query(Channel).filter_by(id=channel.id).first()
            if text_channel_object is None:
                return False
        session.delete(text_channel_object)
        session.commit()
        return True


class Message(Base):
    __tablename__ = "message"
    id = Column(BigInteger, primary_key=True)
    channel_id = Column(BigInteger, ForeignKey("channel.id"))
    channel = relationship(Channel, backref="messages")
    guild_id = Column(BigInteger, ForeignKey("guild.id"))
    user_id = Column(BigInteger, ForeignKey("user.id"))
    content = Column(String(2000))
    embed_json = Column(String(7000))
    timestamp = Column(DateTime)
    deleted = Column(Boolean)

    @classmethod
    def from_discord(cls, session, message: discord.Message):
        channel = Channel.from_discord(session, message.channel)
        _ = User.from_discord(session, message.author)
        with session.no_autoflush, message_lock:
            message_object = session.query(Message).filter_by(id=message.id).first()
            if message_object is None:
                message_object = Message(id=message.id)
                session.add(message_object)
        message_object.user_id = message.author.id
        message_object.channel = channel
        message_object.guild_id = channel.guild_id
        message_object.content = message.content
        message_object.timestamp = message.created_at
        if len(message.embeds) > 0:
            embed = message.embeds[0]
            message_object.embed_json = json.dumps(embed.to_dict())
        message_object.deleted = False
        session.commit()
        return message_object

    @classmethod
    def mark_deleted_id(cls, session, message_id):
        message_object = session.query(Message).filter_by(id=message_id).first()
        if message_object is None:
            return False
        message_object.deleted = True
        session.commit()
        return True


class MessageEdit(Base):
    __tablename__ = "message_edit"
    timestamp = Column(DateTime, primary_key=True)
    message_id = Column(BigInteger, ForeignKey("message.id"), primary_key=True)
    message = relationship("Message", backref="edits")
    edited_content = Column(String(2000))
    edited_embed_json = Column(String(7000))

    @classmethod
    def from_discord(cls, session, message: discord.Message):
        message_object = Message.from_discord(session, message)
        if message.edited_at is None:
            return False
        with session.no_autoflush, edit_lock:
            edit_object = session.query(MessageEdit).filter_by(message_id=message.id).order_by(
                MessageEdit.timestamp.desc()).first()
            if edit_object is None or edit_object.timestamp != message.edited_at.replace(tzinfo=None, microsecond=0):
                edit_object = MessageEdit(timestamp=message.edited_at.replace(tzinfo=None, microsecond=0),
                                          message_id=message.id)
                session.add(edit_object)
        edit_object.message = message_object
        edit_object.edited_content = message.content
        if len(message.embeds) > 0:
            embed = message.embeds[0]
            edit_object.edited_embed_json = json.dumps(embed.to_dict())
        session.commit()
        return edit_object

    @classmethod
    def from_raw(cls, session, message_id, edited_at, content=None, embeds=None):
        if embeds is None:
            embeds = []
        edited_at = edited_at.replace(tzinfo=None, microsecond=0)
        with session.no_autoflush, edit_lock:
            message_object = session.query(Message).filter_by(id=message_id).first()
            if message_object is None:
                return None
            edit_object = session.query(MessageEdit).filter_by(message_id=message_id).order_by(
                MessageEdit.timestamp.desc()).first()
            if edit_object is None or edit_object.timestamp != edited_at:
                edit_object = MessageEdit(timestamp=edited_at, message_id=message_id)
                session.add(edit_object)
        edit_object.message = message_object
        edit_object.edited_content = content
        if len(embeds) > 0:
            embed = embeds[0]
            edit_object.edited_embed_json = json.dumps(embed)
        session.commit()
        return edit_object
