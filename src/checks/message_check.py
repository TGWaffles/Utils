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


def question_check(author):
    def check_author(message):
        return message.author.id == author.id

    return check_author


def check_pinned(message):
    return not message.pinned


def check_trusted_reaction(author, message_id):
    def check_author(reaction, user):
        return user == author and str(reaction.emoji) == '👍' and reaction.message.id == message_id
    return check_author
