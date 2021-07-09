from discord.ext.commands import MinimalHelpCommand

from src.helpers.paginator import Paginator


class UtilsHelp(MinimalHelpCommand):
    def __init__(self, bot, **options):
        print(options)
        super().__init__(**options)
        self.paginator = Paginator(bot=bot, channel=None)

    async def send_pages(self):
        self.paginator.channel = self.get_destination()
        await self.paginator.start()
