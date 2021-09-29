from hikari.errors import ForbiddenError
import a2s
import valve.rcon
import valve.source.a2s
from utils.servers.base import BaseServer
import asyncio


class A2SCompatibleServer(BaseServer):
    def __init__(self, bot, process, *args, **kwargs):
        super().__init__(bot, process, *args, **kwargs)
        self._repr = "A2S-Compatible Server"
        self.query_port = kwargs.setdefault('query_port', self.port)
        self.readable_name = kwargs.setdefault('name', 'A2S-Compatible Server')

    async def update_server_information(self):
        while self.proc.is_running() and self.bot.is_alive:
            try:
                info = await a2s.ainfo((self.ip, self.query_port))

                cur_p = info.player_count
                chat_status = f"Playing: {self.readable_name} | ({cur_p} player{'s' if cur_p != 1 else ''})"
                for chan in self.bot.chat_channels_obj:
                    await chan.edit(topic=chat_status)
                await self.bot.update_presence(status=f"{self.readable_name} | "
                                                      f"({cur_p} player{'s' if cur_p != 1 else ''} online) | "
                                                      f"CPU: {self.proc.cpu_percent(interval=0.1)}% | "
                                                      f"Mem: {round(self.proc.memory_percent(), 2)}%")
            except ForbiddenError:
                print("Bot lacks permission to edit channels. (hikari.ForbiddenError)")
            except valve.source.a2s.NoResponseError:
                print("No Response from server before timeout (NoResponseError)")
            except Exception as e:
                print(f"Error: {e} {type(e)}")
            await asyncio.sleep(30)
