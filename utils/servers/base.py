import asyncio
import datetime

import hikari
import psutil


class BaseServer:
    def __init__(self, bot, process: psutil.Process, *args, **kwargs):
        self.bot = bot
        self.proc = process
        self.name = kwargs.pop('name', 'a game')
        self.ip = kwargs.pop('ip', '127.0.0.1')
        self.port = kwargs.pop('port', 22222)
        self.password = kwargs.pop('rcon_password') if kwargs.get('rcon_password') else kwargs.pop(
            'rcon') if kwargs.get('rcon') else self.bot.cfg["default_rcon_password"]
        self.working_dir = kwargs.pop('folder', '')
        self._repr = "a game"

        self.rcon_port = kwargs.pop('rcon_port', 22232)
        self.rcon = None
        self.rcon_lock = asyncio.Lock()
        self.last_reconnect = datetime.datetime(1, 1, 1)

        if self.__class__.__name__ == 'BaseServer':
            self.bot.loop.create_task(self.update_server_information())

    def __repr__(self):
        return self._repr

    def is_running(self) -> bool:
        return self.proc.is_running()

    async def _log_loop(self):
        pass

    async def chat_from_game_to_guild(self):
        pass

    async def chat_from_guild_to_game(self):
        pass

    async def update_server_information(self):
        await self.bot.update_presence(activity=hikari.Activity(name=self.name, type=0))

    async def sleep_with_backoff(self, tries, wait_time=5):
        await asyncio.sleep(wait_time * tries)
        # if self.bot.debug:
        #     self.bot.bprint("sleep_with_backoff ~ Done waiting for backoff")

    @property
    def status(self) -> psutil.Process:
        return self.proc

    @property
    def players(self) -> int:
        return 0

    def is_chat_channel(self, m: hikari.events.GuildMessageCreateEvent) -> bool:
        for chan in self.bot.chat_channels:
            if chan == m.channel_id:
                return True
        else:
            return False
