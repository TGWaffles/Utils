import asyncio


def get_protocol(bot):
    class ReceiveChrisProtocol(asyncio.Protocol):
        def data_received(self, data: bytes) -> None:
            message = data.decode()
            print(message)
            member_id, content = message.split("\n\n\n")
            bot.bot.loop.create_task(bot.speak_id_content(int(member_id), content))

    return ReceiveChrisProtocol


async def start_server(bot):
    loop = bot.bot.loop
    server = await loop.create_server(get_protocol(bot), '0.0.0.0', 43022)
    async with server:
        await server.serve_forever()
