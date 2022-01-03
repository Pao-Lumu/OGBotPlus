import asyncio
import logging
import re
from typing import List

import docker.models.containers

from utils.servers.docker_base import BaseDockerServer


class TerrariaDockerServer(BaseDockerServer):
    def __init__(self, bot, process, **kwargs):
        super(BaseDockerServer, self).__init__(bot, process, **kwargs)
        self.proc: docker.models.containers.Container = process
        self.bot.loop.create_task(self.chat_from_game_to_guild())
        self.bot.loop.create_task(self.chat_from_guild_to_game())
        self.bot.loop.create_task(self.wait_for_death())
        # if self.__class__.__name__ == 'BaseServer':
        #     self.loop.create_task(self.update_server_information())
        #     self.loop.create_task(self.wait_for_death())

    async def chat_from_game_to_guild(self):
        logging.debug("chat_from_game_to_guild")

        while self.is_running() and self.bot.is_alive:
            try:
                await self.read_server_log()
                await asyncio.sleep(1)
            except Exception as e:
                print(e)
                await asyncio.sleep(.1)

    # async def chat_from_guild_to_game(self):
    #     self.proc.attach()

    async def read_server_log(self):
        watcher = await asyncio.create_subprocess_shell(cmd=f"docker logs -f --tail 0 --since 0m {self.proc.id}",
                                                        stdout=asyncio.subprocess.PIPE)
        while self.is_running() and self.bot.is_alive:
            await asyncio.wait([self._read_stream(self, watcher.stdout, self.process_server_messages)])
        pass

    async def process_server_messages(self, out: List[str]):
        # server_filter = re.compile(
        # r"INFO]:?(?:.*tedServer]:)? (\[[^]]*: .*].*|(?<=]:\s).* the game|.* has made the .*)")
        server_filter = re.compile(
            r"\s .* has (joined|left)")
        # player_filter = re.compile(r"FO]:?(?:.*tedServer]:)? (\[Server].*|<.*>.*)")
        player_filter = re.compile(r"")
        # msgs = []
        # mentioned_users = []
        # for line in out:
        #     raw_player_msg: List[Optional[str]] = regex.findall(player_filter, line)
        #     raw_server_msg: List[Optional[str]] = regex.findall(server_filter, line)
        #
        #     if raw_player_msg:
        #         ret = self.check_for_mentions(raw_player_msg[0])
        #         mentioned_users += ret[0]
        #         msgs.append((ret[1], mentioned_users))
        #     elif raw_server_msg:
        #         msgs.append((f'`{raw_server_msg[0].rstrip()}`', None))
        #     else:
        #         continue
        # if msgs:
        #     x = "\n".join(list(zip(*msgs))[0])
        #     for chan in self.bot.chat_channels_obj:
        #         await chan.send(x, user_mentions=mentioned_users)
        # for msg in msgs:
        #     self.bot.bprint(f"{self._repr} | {''.join(msg[0])}")

    # def is_running(self) -> bool:
    #     logging.debug("is_running")
    #     self.proc.reload()
    #     if self.proc.status == 'running':
    #         return True
    #     else:
    #         return False

    # async def wait_for_death(self):
    #     # print('waiting for the server to DIE')
    #     while True:
    #         self.proc.reload()
    #         if self.proc.status == 'running':
    #             await asyncio.sleep(5)
    #         else:
    #             await asyncio.sleep(2)
    #             break
    #     self.teardown()
    #     logging.debug('killed server object for ' + self.__repr__())
