import asyncio
import logging
from typing import List

import docker.errors
import requests.exceptions

from utils.servers.base import BaseServer


class BaseDockerServer(BaseServer):
    def __init__(self, bot, process, **kwargs):
        super(BaseDockerServer, self).__init__(bot, process, **kwargs)

        if self.__class__.__name__ == 'BaseDockerServer':
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
            await asyncio.wait([self._read_stream(self, watcher.stdout, self.process_server_messages)])
        pass

    @staticmethod
    async def _read_stream(self, stream: asyncio.streams.StreamReader, cb):
        while True:
            await asyncio.sleep(3)
            try:
                raw = await asyncio.wait_for(stream.read(n=7000), .5)
                raw_str = raw.decode('utf-8')
                lines = raw_str.split('\r\n')
                if lines:
                    await cb(lines)
            except asyncio.exceptions.TimeoutError:
                continue
            except Exception as e:
                print(type(e))
                print(e)

    async def process_server_messages(self, text: List[str]):
        pass

    def is_running(self) -> bool:
        logging.debug("checking if server is running")
        try:
            self.proc.reload()
            if self.proc.status == 'running':
                return True
            else:
                return False
        except requests.exceptions.HTTPError:
            return False
        except docker.errors.NotFound:
            return False

    async def wait_for_death(self):
        logging.debug('waiting for the server to DIE')
        while True:
            try:
                self.proc.reload()
                if self.proc.status == 'running':
                    await asyncio.sleep(5)
                else:
                    await asyncio.sleep(2)
                    break
            except requests.exceptions.HTTPError:
                break
            except docker.errors.NotFound:
                logging.info("Docker container no longer found. Possibly shut down.")
                pass
        self.teardown()
        logging.debug('killed server object for ' + self.__repr__())
