import asyncio

import psutil

from utils.servers.a2s import A2SCompatibleServer


class ValheimServer(A2SCompatibleServer):
    def __init__(self, bot, process: psutil.Process, **kwargs):
        super().__init__(bot, process, **kwargs)
        self.query_port = self.port + 1
        self.game = kwargs.pop('game', 'vhserver')
        self.bot.loop.create_task(self.update_server_information())
        self._repr = "Valheim"
        self.readable_name = kwargs.setdefault('name', 'Valheim Server')

        asyncio.ensure_future(self.loop.run_in_executor(None, self.wait_or_when_cancelled))

    def teardown(self):
        self.bot.games.pop(str(self.query_port))
        super().teardown()
