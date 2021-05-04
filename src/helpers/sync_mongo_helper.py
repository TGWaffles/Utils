import pymongo
import datetime
from src.storage import config


def get_client():
    client = pymongo.MongoClient(config.mongo_connection_uri)
    return client


def get_guild_score(guild_id):
    client = get_client()
    discord_db = client.discord
    now = datetime.datetime.now()
    last_week = now - datetime.timedelta(days=7)
    last_valid = {}
    scores = {}
    guild_members_pipeline = [
        {
            "$match": {
                "_id.guild_id": guild_id,
                "deleted": False
            }
        },
        {
            "$lookup": {
                "from": "users",
                "localField": "_id.user_id",
                "foreignField": "_id",
                "as": "user"
            }
        },
        {
            "$match": {
                "user.bot": False
            }
        },
        {
            "$project": {"_id": "$_id"}
        }
    ]
    excluded_channels = discord_db.channels.find({"excluded": True, "guild_id": guild_id}).distinct("_id")
    aggregation = discord_db.members.aggregate(guild_members_pipeline)
    member_list = set(x.get("_id").get("user_id") for x in aggregation)
    query = discord_db.messages.find({"created_at": {"$gt": last_week}, "guild_id": guild_id})
    query.sort("created_at", pymongo.ASCENDING)
    for message in query:
        user_id = message.get("user_id")
        timestamp = message.get("created_at")
        channel_id = message.get("channel_id")
        if user_id not in member_list or channel_id in excluded_channels:
            continue
        if user_id not in last_valid:
            last_valid[user_id] = timestamp
            scores[user_id] = 1
        elif (timestamp - last_valid[user_id]).total_seconds() >= 60:
            last_valid[user_id] = timestamp
            scores[user_id] += 1
    list_of_tuples = [(user_id, score) for user_id, score in scores.items()]
    list_of_tuples.sort(key=lambda x: x[1], reverse=True)
    return list_of_tuples


def get_user_score(user_id, guild_id):
    client = get_client()
    discord_db = client.discord
    now = datetime.datetime.now()
    last_week = now - datetime.timedelta(days=7)
    score = 0
    last_message = datetime.datetime(2015, 1, 1)
    excluded_channels = discord_db.channels.find({"excluded": True, "guild_id": guild_id}).distinct("_id")
    query = discord_db.messages.find({"created_at": {"$gt": last_week}, "guild_id": guild_id, "user_id": user_id})
    for message in query:
        timestamp = message.get("created_at")
        channel_id = message.get("channel_id")
        if channel_id in excluded_channels:
            continue
        if (timestamp - last_message).total_seconds() >= 60:
            last_message = timestamp
            score += 1
    return score
