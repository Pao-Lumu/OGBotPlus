import asyncio
import datetime
import logging

import hikari
import psutil


class BaseServer:
    def __init__(self, bot, process: psutil.Process, **kwargs):
        self.bot = bot
        self.proc: psutil.Process = process
        self.name: str = kwargs.pop('name', 'a game')
        self.ip: str = kwargs.pop('ip', '127.0.0.1')
        self.port: int = int(kwargs.pop('port', 22222))
        self.password: str = kwargs.pop('rcon_password') if kwargs.get('rcon_password') else kwargs.pop(
            'rcon') if kwargs.get('rcon') else self.bot.cfg["default_rcon_password"]
        self.working_dir: str = kwargs.pop('folder', '')
        self._repr: str = "a game"
        self.loop = asyncio.get_running_loop()

        self.rcon_port: int = int(kwargs.pop('rcon_port', 22232))
        self.rcon = None
        self.rcon_lock = asyncio.Lock()
        self.last_reconnect: datetime.datetime = datetime.datetime(1, 1, 1)

        if self.__class__.__name__ == 'BaseServer':
            self.loop.create_task(self.update_server_information())
            self.loop.create_task(self.wait_for_death())

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
        await self.bot.add_game_presence(self.name, self.name)

    @staticmethod
    async def sleep_with_backoff(tries, wait_time=5):
        await asyncio.sleep(wait_time * tries)

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

    async def wait_for_death(self):
        x = True
        proc = await asyncio.create_subprocess_shell(cmd=f"python3 utils/watch.py {self.proc.pid}")
        while x:
            if proc.returncode is None:
                await asyncio.sleep(5)
            else:
                await asyncio.sleep(3)
                x = False
        self.teardown()

    def teardown(self):
        self.bot.games.pop(str(self.port), None)
        asyncio.ensure_future(self.bot.remove_game_presence(self.name))
        asyncio.ensure_future(self.bot.remove_game_chat_info(self.name))
        logging.critical('teardown successful!')
