import discord
import webcolors
from discord.ext import commands


def convert_colour(input_colour):
    input_colour = input_colour.strip('#')
    try:
        colour = input_colour
        int(colour, 16)
        if len(colour) == 3:
            colour = webcolors.normalize_hex("#" + colour).strip('#')
        if len(colour) == 6:
            return discord.Colour.from_rgb(int(colour[:2], 16), int(colour[2:4], 16), int(colour[4:6], 16))
        else:
            raise commands.BadArgument()
    except ValueError:
        try:
            return discord.Colour.from_rgb(*(webcolors.name_to_rgb(input_colour.replace(" ", ""))))
        except ValueError:
            raise commands.BadArgument()
