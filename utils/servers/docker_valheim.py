import asyncio
import re
from typing import List

import a2s
from hikari.errors import ForbiddenError

from utils.servers.docker_base import BaseDockerServer


class ValheimDockerServer(BaseDockerServer):
    def __init__(self, bot, process, **kwargs):
        super(ValheimDockerServer, self).__init__(bot, process, **kwargs)
        self.query_port = self.port + 10
        self.game = kwargs.pop('game', 'vhserver')
        self.bot.loop.create_task(self.update_server_information())
        self._repr = "Valheim"
        self.readable_name = kwargs.setdefault('name', 'Valheim Server In Docker')

    async def update_server_information(self):
        while self.proc.is_running() and self.bot.is_alive:
            try:
                info = await a2s.ainfo((self.ip, self.query_port))

                cur_p = info.player_count
                chat_status = f"{self.readable_name} | ({cur_p} player{'s' if cur_p != 1 else ''})"
                await self.bot.add_game_chat_info(self.name, chat_status)
                status = f"""
{self.readable_name} ({cur_p} player{'s' if cur_p != 1 else ''} online)
"""
                await self.bot.add_game_presence(self.name, status)
            except ForbiddenError:
                print("Bot lacks permission to edit channels. (hikari.ForbiddenError)")
            except a2s.BrokenMessageError:
                print("No Response from server before timeout (NoResponseError)")
            except Exception as e:
                print(f"Error: {e} {type(e)}")
            finally:
                await asyncio.sleep(30)

    async def process_server_messages(self, text: List[str]):
        conn_filter = re.compile('')


