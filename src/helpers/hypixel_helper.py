import math
import PIL.Image
import PIL.ImageDraw
import PIL.ImageFont
import PIL.ImageChops
import aiohttp
import asyncio
import datetime
from io import BytesIO

EASY_LEVELS = 4
EASY_LEVELS_XP = 7000
XP_PER_PRESTIGE = 96 * 5000 + EASY_LEVELS_XP
LEVELS_PER_PRESTIGE = 100
HIGHEST_PRESTIGE = 10
API_URL = "https://api.hypixel.net/"


class HypixelAPI:
    def __init__(self, key):
        self.key = key
        self.request_queue = asyncio.Queue()
        self.process_lock = asyncio.Lock()

    async def safe_request(self, endpoint, parameters=None):
        returned_json = {}
        completed_event = asyncio.Event()
        stored_task = (endpoint, parameters, completed_event, returned_json)
        await self.request_queue.put(stored_task)
        await completed_event.wait()
        return returned_json

    async def queue_loop(self):
        while True:
            waited_event = await self.request_queue.get()
            endpoint, parameters, completed_event, returned_json = waited_event
            if parameters is None:
                parameters = {}
            parameters["key"] = self.key
            async with aiohttp.ClientSession() as session:
                while True:
                    response: aiohttp.ClientResponse = await session.get(f"{API_URL}{endpoint}", params=parameters)
                    try:
                        returned_json.update(await response.json())
                    except aiohttp.ContentTypeError:
                        await asyncio.sleep(5)
                        continue
                    if response.status == 429:
                        sleep_time = int(response.headers.getone("retry-after"))
                        await asyncio.sleep(sleep_time)
                        continue
                    if returned_json.get("cause", "") == "Invalid API key":
                        print("INVALID HYPIXEL API KEY")
                        continue
                    break
            completed_event.set()

    async def get_player(self, uuid):
        uuid = uuid.replace("-", "")
        parameters = {"uuid": uuid}
        data = await self.safe_request("player", parameters)
        if "lastLogout" in data:
            data["lastLogout"] = datetime.datetime.fromtimestamp(data["lastLogout"] / 1000)
        if "lastLogin" in data:
            data["lastLogin"] = datetime.datetime.fromtimestamp(data["lastLogin"] / 1000)
        return data.get("player", {})

    async def get_status(self, uuid):
        uuid = uuid.replace("-", "")
        parameters = {"uuid": uuid}
        data = await self.safe_request("status", parameters)
        return data.get("status", {})


def get_xp_for_level(level):
    if level == 0:
        return 0

    respected_level = get_level_respecting_prestige(level)
    if respected_level > EASY_LEVELS:
        return 5000

    if respected_level < 5:
        return [500, 1000, 2000, 3500][respected_level - 1]
    return 5000


def get_level_respecting_prestige(level):
    if level > HIGHEST_PRESTIGE * LEVELS_PER_PRESTIGE:
        return level - HIGHEST_PRESTIGE * LEVELS_PER_PRESTIGE
    else:
        return level % LEVELS_PER_PRESTIGE


def get_level_from_xp(exp):
    prestiges = math.floor(exp / XP_PER_PRESTIGE)
    level = prestiges * LEVELS_PER_PRESTIGE
    exp_without_prestiges = exp - (prestiges * XP_PER_PRESTIGE)

    for i in range(1, EASY_LEVELS + 1):
        exp_for_easy_level = get_xp_for_level(i)
        if exp_without_prestiges < exp_for_easy_level:
            break

        level += 1
        exp_without_prestiges -= exp_for_easy_level

    return round(level + (exp_without_prestiges / 5000), 2)


def get_colour_from_threat(threat_index):
    if threat_index <= 45:
        return 170, 170, 170
    elif threat_index <= 80:
        return 85, 255, 85
    elif threat_index <= 120:
        return 0, 170, 0
    elif threat_index <= 225:
        return 255, 255, 85
    elif threat_index <= 325:
        return 255, 170, 0
    elif threat_index <= 650:
        return 255, 85, 85
    else:
        return 170, 0, 0


def are_equal(file1, file2):
    image1 = PIL.Image.open(file1)
    image2 = PIL.Image.open(file2)
    diff = PIL.ImageChops.difference(image1, image2)
    file1.seek(0)
    file2.seek(0)
    if diff.getbbox():
        return False
    else:
        return True


def get_file_for_member(member):
    final_file = BytesIO()
    size = 1024
    width = size
    height = width // 4
    if member["online"]:
        fill = (16, 64, 16)
    else:
        fill = (64, 16, 16)
    image = PIL.Image.new('RGB', (width, height), color=fill)
    draw = PIL.ImageDraw.Draw(image)
    name_colour = get_colour_from_threat(member["threat_index"])
    name_font = PIL.ImageFont.truetype("arial.ttf", size // 16)
    name_font.size = size // 16
    # Write Name
    name_x = width // 2
    name_y = height // 8
    draw.text((name_x, name_y), member["name"], font=name_font, anchor="mm", fill=name_colour)
    # Write last online or current game.
    if member["online"]:
        if member["mode"] is None:
            game_text = "{}: \nLOBBY".format(member["game"])
        else:
            try:
                game_text = "{}: \n{} ({})".format(member["game"], member["mode"], member["map"]["map"])
            except KeyError:
                game_text = "{}: \n{}".format(member["game"], member["mode"])
        last_played_heading = "Current Game"
    else:
        last_played_heading = "Last Online"
        game_text = "{}".format(member["last_logout"].strftime("%Y/%m/%d %H:%M"))
    top_line_height = height // 8
    last_played_y = height - top_line_height
    last_played_font = PIL.ImageFont.truetype("arial.ttf", size // 32)
    regular_text_fill = (255, 100, 255)
    last_played_x = width // 64
    # last_played_x = max([draw.textsize(line, font=last_played_font)[0]
    #                      for line in game_text.split("\n")]) // 2 + width // 64
    for line in game_text.split("\n")[::-1]:
        draw.text((last_played_x, last_played_y), line, font=last_played_font, anchor="lm", fill=regular_text_fill,
                  align="center")
        last_played_y -= draw.textsize(line, font=last_played_font)[1]
    draw.text((width // 64, last_played_y), last_played_heading, font=last_played_font, anchor="lm",
              fill=regular_text_fill)
    win_streak = "Winstreak\n{}".format(member["bedwars_winstreak"])
    win_streak_height = top_line_height
    # win_streak_level_x = width - (max([draw.textsize(line, font=last_played_font)[0]
    #                                    for line in win_streak.split("\n")]) // 2 + width // 64)
    win_streak_level_x = width - width // 64
    for line in win_streak.split("\n"):
        draw.text((win_streak_level_x, win_streak_height), line,
                  font=last_played_font, anchor="rm", fill=regular_text_fill)
        win_streak_height += draw.textsize(line, font=last_played_font)[1]
    level_height = height - top_line_height
    level_text = "Level\n{}".format(member["bedwars_level"])
    for line in level_text.split("\n")[::-1]:
        draw.text((win_streak_level_x, level_height), line,
                  font=last_played_font, anchor="rm", fill=regular_text_fill)
        level_height -= draw.textsize(line, font=last_played_font)[1]

    # fkdr_x = max([-(win_streak_level_x-width), last_played_x])
    fkdr_x = width // 64
    fkdr_text = "FKDR\n{}".format(round(member["fkdr"], 2))
    fkdr_height = top_line_height
    for line in fkdr_text.split("\n"):
        draw.text((fkdr_x, fkdr_height), line, font=last_played_font, anchor="lm",
                  fill=regular_text_fill, aligh="center")
        fkdr_height += draw.textsize(line, font=last_played_font)[1]

    threat_index_x = width // 2
    threat_index_y = height // 2

    threat_index_text = "Threat Index\n{}".format(round(member["threat_index"], 1))
    draw.text((threat_index_x, threat_index_y), threat_index_text, font=last_played_font, anchor="mm",
              fill=regular_text_fill, align="center")
    image.save(fp=final_file, format="png")
    final_file.seek(0)
    return final_file
