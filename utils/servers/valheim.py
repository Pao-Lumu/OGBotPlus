import asyncio

import psutil

from utils.servers.a2s import A2SCompatibleServer


class ValheimServer(A2SCompatibleServer):
    def __init__(self, bot, process: psutil.Process, **kwargs):
        super().__init__(bot, process, **kwargs)
        self.game = kwargs.pop('game', 'vhserver')
        self.bot.loop.create_task(self.chat_from_game_to_guild())
        self.bot.loop.create_task(self.chat_from_guild_to_game())
        self.bot.loop.create_task(self.update_server_information())
        self.log = list()
        self.log_lock = asyncio.Lock()
        self.bot.loop.create_task(self._log_loop())
        self._repr = "Valheim"
        self.readable_name = kwargs.setdefault('name', 'Valheim Server')

        self.logs = kwargs.pop('logs')