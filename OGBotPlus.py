import datetime
from abc import ABC

import hikari
import lightbulb
import typing
from typing import Dict, Optional, List, Iterable, Any, Union
import asyncio
from colorama import Fore
from utils.servers.base import BaseServer


class OGBotPlus(lightbulb.Bot, ABC):
    def __init__(self,
                 config: dict,
                 intents: hikari.Intents,
                 prefix: str,
                 owner_ids: Iterable[int],
                 ignore_bots: bool,
                 **kwargs):
        self.cfg: Dict = config
        self.main_guilds: List[int] = config['main_guilds']
        self.chat_channels: List[int] = config['chat_channels']
        self.santa_channel: int = config['santa_channel']
        self.games: Dict[str, BaseServer] = dict()
        self.game_statuses: Dict[str, str] = {}
        self.game_chat_info: Dict[str, str] = {}
        self._game_running = asyncio.Event()
        self._game_stopped = asyncio.Event()
        super().__init__(intents=intents, prefix=prefix, owner_ids=owner_ids, ignore_bots=ignore_bots, **kwargs)

    async def wait_until_game_running(self, delay=0):
        await self._game_running.wait()
        if delay:
            await asyncio.sleep(delay)

    async def wait_until_game_stopped(self, delay=0):
        await self._game_stopped.wait()
        if delay:
            await asyncio.sleep(delay)

    async def add_game_presence(self, game_name: str, activity: str):
        self.game_statuses[game_name] = activity

    async def remove_game_presence(self, game_name: str):
        self.game_statuses.pop(game_name, None)

    async def set_game_presence(self):
        while True:
            await asyncio.sleep(15)
            if not self.game_statuses.keys():
                print('nothing')
                continue
            presences = [v for k, v in self.game_statuses]
            activity = hikari.Activity(name="; ".join(presences))
            try:
                await self.update_presence(activity=activity)
            except Exception as e:
                print(e)

    async def add_game_chat_info(self, game_name: str, info: str):
        self.game_chat_info[game_name] = info

    async def remove_game_chat_info(self, game_name: str):
        self.game_statuses.pop(game_name, None)

    async def set_game_chat_info(self):
        while True:
            await asyncio.sleep(15)
            if not self.game_statuses.keys():
                print('nothing')
                continue
            info = [v for k, v in self.game_chat_info]
            print(info)
            try:
                for chan in self.chat_channels_obj:
                    await chan.edit(topic="Playing: " + "; ".join(info))
            except Exception as e:
                print(e)

    @property
    def loop(self):
        return asyncio.get_running_loop()

    @property
    def is_game_running(self) -> bool:
        return self._game_running.is_set()

    @property
    def main_guild_obj(self) -> List[hikari.Guild]:
        return [self.cache.get_guild(guild) for guild in self.main_guilds]

    @property
    def santa_channel_obj(self) -> hikari.GuildChannel:
        return self.cache.get_guild_channel(self.santa_channel)

    @property
    def chat_channels_obj(self) -> List[hikari.GuildChannel]:
        # return [self.cache.get_guild_channel(chan) for chan in self.chat_channels]
        result = []
        for chan in self.chat_channels:
            try:
                result.append(self.cache.get_guild_channel(chan))
            except (hikari.ForbiddenError, hikari.NotFoundError):  # this is just a guess at what it'll raise
                self.bprint(f"Couldn't find channel with id {chan}. It may have been deleted.")
                continue
        return result

    @property
    def is_game_stopped(self):
        return self._game_stopped.is_set()

    def bprint(self, text: Union[str, List[str], Any] = '', *args):
        cur_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        if isinstance(text, list):
            lines = text
        elif isinstance(text, str):
            lines = text.split("\n")
        else:
            lines = str(text).split("\n")

        for line in lines:
            print(f"{Fore.LIGHTYELLOW_EX}{cur_time}{Fore.RESET} ~ {line}", *args)

    def run(self, **kwargs):
        super(OGBotPlus, self).run(**kwargs)
