import datetime

import sqlalchemy
import random
from sqlalchemy import and_, desc, func
from sqlalchemy.orm import sessionmaker, scoped_session

from src.helpers.models.database_models import *


# old_commit = session.Session.commit
# old_query = session.Session.query
#
#
# def commit(self):
#     try:
#         old_commit(self)
#     except IntegrityError as e:
#         session.Session.rollback(self)
#
#
# def query(self, *args, **kwargs):
#     try:
#         return old_query(self, *args, **kwargs)
#     except (OperationalError, StatementError):
#         session.Session.rollback(self)
#         print("ERROR FOUND!")
#         return query(self, *args, **kwargs)
#
#
# session.Session.commit = commit
# session.Session.query = query


class DatabaseHelper:
    def __init__(self):
        self.engine = sqlalchemy.create_engine("mysql://utils:t93PRdtuyWgyt93PRdtuyWgy@elastic.thom.club/"
                                               "utils?charset=utf8mb4")
        session_maker = sessionmaker(bind=self.engine)
        self.session_creator = scoped_session(session_maker)
        self.processing = Lock()

    def ensure_db(self):
        with self.processing:
            Base.metadata.create_all(bind=self.engine)

    def update_member(self, after: discord.Member):
        with self.processing:
            session = self.session_creator()
            Member.update_member(session, after)
            self.session_creator.remove()

    def delete_member(self, member: discord.Member):
        with self.processing:
            session = self.session_creator()
            Member.delete_member(session, member)
            self.session_creator.remove()

    def save_message(self, message: discord.Message):
        with self.processing:
            session = self.session_creator()
            Message.from_discord(session, message)
            self.session_creator.remove()

    def save_message_edit_raw(self, payload):
        with self.processing:
            session = self.session_creator()
            last_edited = payload.data.get('edited_timestamp')
            if last_edited is None:
                return None
            timestamp = datetime.datetime.fromisoformat(last_edited)
            content = payload.data.get("content", None)
            if content == "":
                content = None
            embeds = payload.data.get("embeds", None)
            if payload.data.get("author", {}).get("bot", False):
                return False
            edit_object = MessageEdit.from_raw(session, payload.message_id, timestamp, content, embeds)
            self.session_creator.remove()
            return edit_object

    def save_message_edit(self, message):
        with self.processing:
            if message.author.bot:
                return False
            session = self.session_creator()
            MessageEdit.from_discord(session, message)
            self.session_creator.remove()

    def mark_deleted(self, message_id):
        with self.processing:
            session = self.session_creator()
            Message.mark_deleted_id(session, message_id)
            self.session_creator.remove()

    def channel_updated(self, updated_channel):
        with self.processing:
            session = self.session_creator()
            Channel.from_discord(session, updated_channel)
            self.session_creator.remove()

    def delete_channel(self, channel):
        with self.processing:
            session = self.session_creator()
            Channel.delete_channel(session, channel)
            self.session_creator.remove()

    def user_update(self, user):
        with self.processing:
            session = self.session_creator()
            User.from_discord(session, user)
            self.session_creator.remove()

    def remove_guild(self, guild):
        with self.processing:
            session = self.session_creator()
            Guild.delete(session, guild)
            self.session_creator.remove()

    def add_guild(self, guild):
        with self.processing:
            session = self.session_creator()
            Guild.update_from_discord(session, guild)
            self.session_creator.remove()

    def add_role(self, role):
        with self.processing:
            session = self.session_creator()
            Role.from_discord(session, role)
            self.session_creator.remove()

    def remove_role(self, role):
        with self.processing:
            session = self.session_creator()
            Role.delete(session, role)
            self.session_creator.remove()

    def count(self, guild, phrase):
        with self.processing:
            session = self.session_creator()
            query = session.query(func.count(Message.id)).filter(Message.content.match(phrase),
                                                                 Message.guild_id == guild.id)
            amount = query.first()[0]
            self.session_creator.remove()
        return amount

    def count_member(self, member, phrase):
        with self.processing:
            session = self.session_creator()
            query = session.query(func.count(Message.id)).filter(Message.content.match(phrase),
                                                                 Message.guild_id == member.guild.id,
                                                                 Message.user_id == member.id)
            amount = query.first()[0]
            self.session_creator.remove()
        return amount

    def phrase_times(self, guild, phrase):
        with self.processing:
            session = self.session_creator()
            query = session.query(Message.timestamp).filter(
                Message.content.match(phrase),
                Message.guild_id == guild.id).order_by(
                Message.timestamp)
            print(query.statement.compile(self.engine))
            results = query.all()
            print("Got results")
            times = [row.timestamp for row in results]
            print("extracted from results")
            self.session_creator.remove()
            return times

    def all_messages(self, guild):
        with self.processing:
            session = self.session_creator()
            query = session.query(func.count(Message.id)).filter(Message.guild_id == guild.id)
            amount = query.first()[0]
            self.session_creator.remove()
        return amount

    def get_last_week_messages(self, guild):
        with self.processing:
            session = self.session_creator()
            now = datetime.datetime.now()
            last_week = now - datetime.timedelta(days=7)
            last_valid = {}
            scores = {}
            # total_messages = {}
            query = session.query(Message.user_id,
                                  Message.timestamp).with_hint(Message,
                                                               "USE INDEX(whenMessage)").join(Member, and_(
                Message.user_id == Member.user_id,
                Message.guild_id ==
                Member.guild_id)).join(User, Message.user_id == User.id). \
                filter(Message.timestamp > last_week, Message.guild_id == guild.id,
                       User.bot.is_(False))
            results = sorted(query.all(), key=lambda x: x.timestamp)
            for row in results:
                user_id = row.user_id
                timestamp = row.timestamp
                # total_messages[user_id] = total_messages.get(user_id, 0) + 1
                if user_id not in last_valid:
                    last_valid[user_id] = timestamp
                    scores[user_id] = 1
                elif (timestamp - last_valid[user_id]).total_seconds() >= 60:
                    last_valid[user_id] = timestamp
                    scores[user_id] += 1
            list_of_tuples = [(user_id, score) for user_id, score in scores.items()]
            list_of_tuples.sort(key=lambda x: x[1], reverse=True)
            self.session_creator.remove()
            return list_of_tuples[:12]

    def get_last_week_score(self, member):
        with self.processing:
            session = self.session_creator()
            now = datetime.datetime.now()
            last_week = now - datetime.timedelta(days=7)
            last_valid = datetime.datetime(2015, 1, 1)
            score = 0
            # total_messages = {}
            query = session.query(Message.user_id, Message.timestamp).with_hint(Message,
                                                                                "USE INDEX(whenMessage)").filter(
                Message.timestamp > last_week,
                Message.user_id == member.id,
                Message.guild_id ==
                member.guild.id).order_by(
                Message.timestamp)
            results = query.all()
            for row in results:
                timestamp = row.timestamp
                # total_messages[user_id] = total_messages.get(user_id, 0) + 1
                if (timestamp - last_valid).total_seconds() >= 60:
                    last_valid = timestamp
                    score += 1
            self.session_creator.remove()
            return score

    def snipe(self, channel):
        with self.processing:
            session = self.session_creator()
            sub_query = session.query(Message).with_hint(Message, "USE INDEX(snipe)").filter(
                Message.channel_id == channel.id, Message.deleted.is_(True)).subquery()
            query = session.query(sub_query).order_by(
                desc(sub_query.c.timestamp)).limit(1)
            print(query.statement.compile(self.engine))
            self.session_creator.remove()
            return query.first()

    def get_graph_of_messages(self, member):
        with self.processing:
            session = self.session_creator()
            query = session.query(Message.timestamp).with_hint(Message,
                                                               "USE INDEX(whenMessage)").filter(
                Message.user_id == member.id,
                Message.guild_id ==
                member.guild.id).order_by(
                Message.timestamp)
            results = query.all()
            times = [row.timestamp for row in results]
            self.session_creator.remove()
            return times

    def select_random(self, guild):
        with self.processing:
            session = self.session_creator()
            now = datetime.datetime.now()
            last_week = now - datetime.timedelta(days=7)
            sub_query = session.query(func.distinct(Message.user_id).label("user_id")).with_hint(Message,
                                                                                                 "USE INDEX(timestamp)").filter(
                Message.timestamp > last_week, Message.guild_id == guild.id).subquery()
            query = session.query(sub_query.c.user_id).order_by(func.rand()).limit(1)
            results = query.all()
            return results[0][0]
