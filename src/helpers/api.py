import asyncio
import json
from src.helpers.storage_helper import DataHelper


def get_protocol(bot):
    class ReceiveAPIMessage(asyncio.Protocol):
        def data_received(self, data: bytes) -> None:
            json_content = json.loads(data.decode())
            storage = DataHelper()
            if json_content.get("key", "") not in storage.get("api_keys", {}).keys():
                return
            if json_content.get("type", "") == "tts_message":
                content = json_content.get("message_content", "")
                try:
                    member_id = int(storage.get("api_keys", {}).get(json_content.get("key", "")))
                except ValueError:
                    return
                bot.bot.loop.create_task(bot.speak_id_content(int(member_id), content))
    return ReceiveAPIMessage


async def start_server(bot):
    loop = bot.bot.loop
    server = await loop.create_server(get_protocol(bot), '0.0.0.0', 43023)
    async with server:
        await server.serve_forever()
