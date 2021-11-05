import asyncio
import logging

from utils.servers.base import BaseServer


class BaseDockerServer(BaseServer):
    def __init__(self, bot, process, **kwargs):
        super(BaseDockerServer, self).__init__(bot, process, **kwargs)

        if self.__class__.__name__ == 'BaseServer':
            self.loop.create_task(self.update_server_information())
            self.loop.create_task(self.wait_for_death())

    async def chat_from_game_to_guild(self):
        logging.debug("chat_from_game_to_guild")

        while self.is_running() and self.bot.is_alive:
            try:
                await self.read_server_log()
                await asyncio.sleep(1)
            except Exception as e:
                print(e)
                await asyncio.sleep(.1)

    async def read_server_log(self):
        watcher = await asyncio.create_subprocess_shell(cmd=f"docker logs -f --tail 0 --since 0m {self.proc.id}",
                                                        stdout=asyncio.subprocess.PIPE)
        while self.is_running() and self.bot.is_alive:
            await asyncio.wait([self._read_stream(watcher.stdout, self.process_server_messages)])
        pass

    @staticmethod
    async def _read_stream(stream: asyncio.streams.StreamReader, cb):
        lines = []
        while True:
            try:
                line = await asyncio.wait_for(stream.readuntil(), timeout=3)
                lines.append(line.decode('utf-8'))
            except asyncio.exceptions.TimeoutError:
                if lines:
                    await cb(lines)
                    lines = []

    def is_running(self) -> bool:
        logging.debug("is_running")
        self.proc.reload()
        if self.proc.status == 'running':
            return True
        else:
            return False

    async def wait_for_death(self):
        # print('waiting for the server to DIE')
        while True:
            self.proc.reload()
            if self.proc.status == 'running':
                await asyncio.sleep(5)
            else:
                await asyncio.sleep(2)
                break
        self.teardown()
        logging.debug('killed server object for ' + self.__repr__())

    async def process_server_messages(self, text):
        pass
