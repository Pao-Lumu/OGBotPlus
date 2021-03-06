import asyncio

import a2s
from hikari.errors import ForbiddenError

from utils.servers.base import BaseServer


class A2SCompatibleServer(BaseServer):
    def __init__(self, bot, process, **kwargs):
        super().__init__(bot, process, **kwargs)
        self._repr = "A2S-Compatible Server"
        self.query_port = kwargs.setdefault('query_port', self.port)
        self.readable_name = kwargs.setdefault('name', 'A2S-Compatible Server')
        self.loop.create_task(self.wait_for_death())

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
            except Exception as e:
                print(f"Error: {e} {type(e)}")
            finally:
                await asyncio.sleep(30)
