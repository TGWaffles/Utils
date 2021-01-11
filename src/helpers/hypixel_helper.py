import math

EASY_LEVELS = 4
EASY_LEVELS_XP = 7000
XP_PER_PRESTIGE = 96 * 5000 + EASY_LEVELS_XP
LEVELS_PER_PRESTIGE = 100
HIGHEST_PRESTIGE = 10


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

