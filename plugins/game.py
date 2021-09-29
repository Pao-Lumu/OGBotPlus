# noinspection PyPackageRequirements

# from utils import helpers
import asyncio
import functools

import lightbulb
import psutil

from utils import sensor
from utils.servers import minecraft, valheim, source, base
from OGBotPlus import OGBotPlus
import hikari


class Game(lightbulb.Plugin):

    def __init__(self, bot: OGBotPlus):
        self.bot = bot
        super().__init__()

    @lightbulb.listener(hikari.events.ShardReadyEvent)
    async def on_start(self, _):
        asyncio.get_running_loop().create_task(self.check_server_running())
        asyncio.get_running_loop().create_task(self.get_current_server_status())

    @staticmethod
    def wait_or_when_cancelled(process):
        bot_proc = psutil.Process()
        while True:
            try:
                process.wait(timeout=1)
                return
            except psutil.TimeoutExpired:
                if bot_proc.is_running():
                    continue
                else:
                    return

    async def check_server_running(self):
        await asyncio.sleep(5)
        while self.bot.is_alive:
            try:
                await asyncio.sleep(1)
                process, data = sensor.get_game_info()
                if process and data:
                    self.bot._game_stopped.clear()
                    self.bot._game_running.set()
                    self.bot.game.info = data

                    self.bot.bprint(f"Server Status | Now Playing: {data['name']}")
                    await self.bot.loop.run_in_executor(None, functools.partial(self.wait_or_when_cancelled, process))
                    self.bot.bprint(f"Server Status | Offline")

                    self.bot._game_running.clear()
                    self.bot._game_stopped.set()
                    self.bot.game.info = None
            except ProcessLookupError:
                await asyncio.sleep(5)
                continue
            except ValueError:
                await asyncio.sleep(5)
                continue
            except AttributeError:
                await asyncio.sleep(5)
                continue
            except Exception as e:
                print(str(type(e)) + ": " + str(e))
                print("This is from the server checker")

    async def get_current_server_status(self):
        await self.bot.wait_until_game_running(1)
        self.bot.game = None
        while self.bot.is_alive:
            # If game is running upon instantiation
            if self.bot.is_game_running:
                process, data = sensor.get_game_info()
                self.bot.game = generate_server_object(self.bot, process, data)
                await self.bot.wait_until_game_stopped(2)

            # Elif no game is running upon instantiation:
            elif self.bot.is_game_stopped:
                self.bot.game = None
                await self.bot.update_presence()
                await self.bot.wait_until_game_running(2)


def generate_server_object(bot, process, gameinfo: dict) -> base.BaseServer:
    if 'java' in gameinfo['executable'].lower() and (
            'forge' in ' '.join(gameinfo['command'])
            or 'server.jar' in ' '.join(gameinfo['command'])
            or gameinfo['game'] == "minecraft"
            or 'nogui' in ' '.join(gameinfo['command'])):  # words cannot describe how scuffed this is.
        print("Found Minecraft")
        return minecraft.MinecraftServer(bot, process, **gameinfo)
    elif 'srcds' in gameinfo['executable'].lower():
        return source.SourceServer(bot, process, **gameinfo)
    elif 'valheim_server' in gameinfo['executable'].lower():
        return valheim.ValheimServer(bot, process, **gameinfo)
    else:
        print("Didn't find server... hm.")
