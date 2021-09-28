import datetime
from abc import ABC

import hikari
import lightbulb
import typing
import asyncio
from lightbulb import help as help_
from colorama import Fore


class OGBotPlus(lightbulb.Bot, ABC):
    def __init__(self, main_guild=0, chat_channel=0, santa_channel=0, **kwargs):
        self.main_guild: int = main_guild
        self.chat_channel: int = chat_channel
        self.santa_channel: int = santa_channel

        self._game_running = asyncio.Event()
        self._game_stopped = asyncio.Event()
        super().__init__(**kwargs)

    async def wait_until_game_running(self, delay=0):
        await self._game_running.wait()
        if delay:
            await asyncio.sleep(delay)

    async def wait_until_game_stopped(self, delay=0):
        await self._game_stopped.wait()
        if delay:
            await asyncio.sleep(delay)

    @property
    def loop(self):
        return asyncio.get_running_loop()

    @property
    def is_game_running(self):
        return self._game_running.is_set()

    # @property
    # def main_guild(self):
    #     return self.cache.get_guild(self.__main_guild)
    #
    # @property
    # def santa_channel(self):
    #     return self.cache.get_guild_channel(self.__santa_channel)
    #
    # @property
    # def chat_channel(self):
    #     return self.cache.get_guild_channel(self.__chat_channel)

    @property
    def is_game_stopped(self):
        return self._game_stopped.is_set()

    def bprint(self, text: str = '', *args):
        cur_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        lines = text.split("\n")
        for line in lines:
            print(f"{Fore.LIGHTYELLOW_EX}{cur_time}{Fore.RESET} ~ {line}", *args)

    def run(self, **kwargs):
        super(OGBotPlus, self).run(**kwargs)
