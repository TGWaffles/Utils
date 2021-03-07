import json
import os

from aiohttp import web

from src.storage.token import api_token

routes = web.RouteTableDef()


async def is_unauthorised(request):
    try:
        request_json = await request.json()
    except (TypeError, json.JSONDecodeError):
        return web.Response(status=400)
    if request_json.get('token', "") != api_token:
        return web.Response(status=401)


@routes.post("/restart")
async def restart(request: web.Request):
    unauthorised_response = await is_unauthorised(request)
    if unauthorised_response is not None:
        return unauthorised_response
    os.system("tmux kill-session -t MonkeyDB")
    os.system("tmux new -d -s MonkeyDB sh start.sh")
    return web.Response(status=202)


@routes.post("/update")
async def update(request: web.Request):
    unauthorised_response = await is_unauthorised(request)
    if unauthorised_response is not None:
        return unauthorised_response
    os.system("git pull")
    return web.Response(status=202)


if __name__ == '__main__':
    app = web.Application()
    app.add_routes(routes)
    web.run_app(app, port=6969)
