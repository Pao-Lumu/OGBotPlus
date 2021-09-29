import datetime
from abc import ABC

import hikari
import lightbulb
import typing
import asyncio
from lightbulb import help as help_
from colorama import Fore
from utils.servers.base import BaseServer


class OGBotPlus(lightbulb.Bot, ABC):
    def __init__(self, config: dict, intents: hikari.Intents, prefix: str, owner_ids: typing.Iterable[int], **kwargs):
        self.cfg: typing.Dict = config
        self.main_guilds: typing.List[int] = config['main_guilds']
        self.chat_channels: typing.List[int] = config['chat_channels']
        self.santa_channel: int = config['santa_channel']
        self.game: typing.Optional[BaseServer] = None

        self._game_running = asyncio.Event()
        self._game_stopped = asyncio.Event()
        super().__init__(intents=intents, prefix=prefix, owner_ids=owner_ids, **kwargs)

    async def wait_until_game_running(self, delay=0):
        await self._game_running.wait()
        if delay:
            await asyncio.sleep(delay)

    async def wait_until_game_stopped(self, delay=0):
        await self._game_stopped.wait()
        if delay:
            await asyncio.sleep(delay)

    # @property
    # def loop(self):
    #     return asyncio.get_running_loop()

    @property
    def is_game_running(self) -> bool:
        return self._game_running.is_set()

    @property
    def main_guild_obj(self) -> typing.List[hikari.Guild]:
        return [self.cache.get_guild(guild) for guild in self.main_guilds]

    @property
    def santa_channel_obj(self) -> hikari.GuildChannel:
        return self.cache.get_guild_channel(self.santa_channel)

    @property
    def chat_channels_obj(self) -> typing.List[hikari.GuildChannel]:
        return [self.cache.get_guild_channel(chan) for chan in self.chat_channels]

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
