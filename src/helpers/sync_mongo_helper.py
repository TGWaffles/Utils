import pymongo
import datetime

client = pymongo.MongoClient('mongodb://192.168.1.100:27017,'
                             '192.168.1.20:27017,'
                             '192.168.1.135:27017/?replicaSet=thomasRep0')


def get_guild_score(guild_id):
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
    aggregation = discord_db.members.aggregate(guild_members_pipeline)
    member_list = set(x.get("_id").get("user_id") for x in await aggregation.to_list(length=None))
    query = discord_db.messages.find({"created_at": {"$gt": last_week}, "guild_id": guild_id})
    query.sort("created_at", pymongo.ASCENDING)
    async for message in query:
        user_id = message.get("user_id")
        timestamp = message.get("created_at")
        if user_id not in member_list:
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
