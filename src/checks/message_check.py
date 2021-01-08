def check_reply(author):
    def check_author(message):
        return message.author.id == author.id and message.content.lower() == "yes"
    return check_author


def check_pinned(message):
    return not message.pinned
