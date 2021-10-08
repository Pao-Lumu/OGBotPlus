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

    @lightbulb.listener(hikari.ShardReadyEvent)
    async def on_start(self, _):
        if not self.loop:
            self.loop = asyncio.get_running_loop()
        if not self.check_server:
            self.check_server = self.loop.create_task(self.check_server_running())
        if not self.get_current_status:
            self.get_current_status = self.loop.create_task(self.get_current_server_status())

    @lightbulb.listener(hikari.GuildMessageCreateEvent)
    async def on_chat_message_in_chat_channel(self, event: hikari.GuildMessageCreateEvent):
        if event.author.is_bot:
            return
        if event.channel_id in self.bot.chat_channels:
            if len(event.message.content) < 1750:
                for chan in self.bot.chat_channels_obj:
                    if chan.id != event.channel_id:
                        await chan.send(
                            f"`{event.author.username} ({event.get_guild().name})`\n{event.message.content}")
            else:
                await event.member.send("The message you sent was too long. `len(event.message.content) > 1750`")

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
        while self.bot.is_alive:
            try:
                await asyncio.sleep(2)
                running_server_data = [(port, *sensor.get_game_info(x)) for port, x in sensor.get_running()]
                print(running_server_data)
                if running_server_data:
                    self.bot._game_stopped.clear()
                    self.bot._game_running.set()
                    for _, process, data in running_server_data:
                        self.bot.bprint(f"Server Status | Now Playing: {data['name']}")
                        await asyncio.sleep(2)
                    await asyncio.gather(
                        *[self.loop.run_in_executor(None, functools.partial(self.wait_or_when_cancelled, process)) for
                          _, process in running_server_data])
                if not running_server_data:
                    self.bot.bprint(f"Server Status | Offline")
                    self.bot._game_running.clear()
                    self.bot._game_stopped.set()
                    self.bot.games = {}
            except (ProcessLookupError, ValueError, AttributeError):
                await asyncio.sleep(5)
                continue
            except Exception as e:
                print(str(type(e)) + ": " + str(e))
                print("This is from the server checker")

    async def get_current_server_status(self):
        await self.bot.wait_until_game_running(1)
        while self.bot.is_alive:
            # If game is running upon instantiation
            if self.bot.is_game_running:
                running = [(port, *sensor.get_game_info(x)) for port, x in sensor.get_running()]
                for port, process, data in running:
                    self.bot.games[port] = generate_server_object(self.bot, process, data)
                await self.bot.wait_until_game_stopped(2)

            # Elif no game is running upon instantiation:
            elif self.bot.is_game_stopped:
                self.bot.games = {}
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
