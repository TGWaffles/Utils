import asyncio
import motor.motor_asyncio
import aiohttp


class MongoDB:
    def __init__(self):
        self.client = motor.motor_asyncio.AsyncIOMotorClient('192.168.1.100', 27017)

    @staticmethod
    async def force_insert(collection, document):
        if "_id" in document:
            await collection.replace_one({"_id": document.get("_id")}, document, upsert=True)
        else:
            await collection.insert_one(document)

    @staticmethod
    async def find_by_id(collection, search_id):
        result = await collection.find_one({"_id": search_id})
        return result

    @staticmethod
    async def find_by_column(collection, column, value):
        result = await collection.find_one({column: value})
        return result

    @staticmethod
    async def fetch_all(collection):
        query = collection.find()
        results = await query.to_list(length=None)
        return results


async def main():
    db = MongoDB()
    client = db.client
    hypixel = client.hypixel
    channels = hypixel.channels

    # print(await db.find_by_id(channels, 798292125027926036))
    print(await channels.distinct("_id"))
    # print([await db.username_from_uuid(uuid) for uuid in await channels.distinct("players")])


if __name__ == '__main__':
    loop = asyncio.get_event_loop()
    loop.create_task(main())
    loop.run_forever()
