from discord.ext.commands import MinimalHelpCommand

from src.helpers.paginator import Paginator


class UtilsHelp(MinimalHelpCommand):
    def __init__(self, **options):
        super().__init__(**options)
        self.paginator = Paginator(bot=None, channel=None)

    async def send_pages(self):
        self.paginator.bot = self.context.bot
        self.paginator.channel = self.get_destination()
        await self.paginator.start()
