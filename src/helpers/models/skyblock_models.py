import asyncio
import enum


class TooLongException(asyncio.TimeoutError):
    pass


class Rarity(enum.Enum):
    ALL = 0
    COMMON = 1
    UNCOMMON = 2
    RARE = 3
    EPIC = 4
    LEGENDARY = 5
    MYTHIC = 6
    SPECIAL = 7
    VERY_SPECIAL = 8
