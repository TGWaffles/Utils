from discord.ext.commands import MinimalHelpCommand

from src.helpers.paginator import Paginator


class UtilsHelp(MinimalHelpCommand):
    def __init__(self, bot, **options):
        super().__init__(**options)
        self.paginator = Paginator(bot=bot, channel=self.get_destination())

    async def send_pages(self):
        await self.paginator.start()
