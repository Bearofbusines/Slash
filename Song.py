from datetime import datetime
from YTDLInterface import YTDLInterface


class Song:
    def __init__(self, interaction, link):
        self.link = link
        self.requester = interaction.user
        self.channel = interaction.channel

        # All of these will be populated when the populate() method is called
        self.title = None
        self.uploader = None
        self.audio = None
        self.id = None
        self.thumbnail = None
        self.duration = None
        self.original_url = None

        # Delta time handling variables
        self.start_time = None
        self.pause_start = None
        self.pause_time = None

    # Populate all None fields
    # @classmethod
    async def populate(self) -> None:
        data = await YTDLInterface.query_link(self.link)
        self.title = data.get('title')
        self.uploader = data.get('channel')
        self.audio = data.get('url')
        self.id = data.get('id')
        self.thumbnail = data.get('thumbnail')
        self.duration = data.get('duration')
        self.original_url = data.get('webpage_url')

    @staticmethod
    def parse_duration(duration: int) -> str:
        minutes, seconds = divmod(duration, 60)
        hours, minutes = divmod(minutes, 60)
        days, hours = divmod(hours, 24)

        duration = []
        if days > 0:
            duration.append(f'{days} days')
        if hours > 0:
            duration.append(f'{hours} hours')
        if minutes > 0:
            duration.append(f'{minutes} minutes')
        if seconds > 0:
            duration.append(f'{seconds} seconds')

        return ', '.join(duration)

    async def pause(self) -> None:
        self.pause_start = datetime.now()
        self.vc.pause()
