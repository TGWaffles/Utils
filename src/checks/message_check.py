from discord.ext.commands.core import _convert_to_bool, BadBoolArgument


def check_reply(author):
    def check_author(message):
        try:
            if message.author.id == author.id:
                _convert_to_bool(message.content)
                return True
        except BadBoolArgument:
            return False
    return check_author


def check_pinned(message):
    return not message.pinned
