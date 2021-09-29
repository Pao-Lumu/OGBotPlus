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
        if psutil.WINDOWS:
            bot.bprint("(Game Plugin) | Windows might be compatible sometimes, but is not supported as a server host.")
        self.bot = bot
        self.loop = None
        self.check_server = None
        self.get_current_status = None
        super().__init__()

    @lightbulb.listener(hikari.events.ShardReadyEvent)
    async def on_start(self, _):
        if not self.loop:
            self.loop = asyncio.get_running_loop()
        if not self.check_server:
            self.check_server = self.loop.create_task(self.check_server_running())
        if not self.get_current_status:
            self.get_current_status = self.loop.create_task(self.get_current_server_status())

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
        await asyncio.sleep(2)
        while self.bot.is_alive:
            try:
                process, data = await asyncio.sleep(1, sensor.get_game_info())
                if process and data:
                    self.bot._game_stopped.clear()
                    self.bot._game_running.set()
                    self.bot.game.info = data
                    print(self.bot.is_game_running)

                    self.bot.bprint(f"Server Status | Now Playing: {data['name']}")
                    await self.loop.run_in_executor(None, functools.partial(self.wait_or_when_cancelled, process))
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
    executable = gameinfo['executable'].lower()
    if gameinfo['game'] == "minecraft" \
            or ('java' in executable and ('forge' in ' '.join(gameinfo['command']))
                or 'server.jar' in ' '.join(gameinfo['command'])
                or 'nogui' in ' '.join(gameinfo['command'])):  # words cannot describe how scuffed this is.
        print("Found Minecraft")
        return minecraft.MinecraftServer(bot, process, **gameinfo)
    elif 'srcds' in executable:
        return source.SourceServer(bot, process, **gameinfo)
    elif 'valheim_server' in executable:
        return valheim.ValheimServer(bot, process, **gameinfo)
    elif 'terraria' in executable:
        pass  # nyi
    else:
        print("Didn't find server... hm.")
