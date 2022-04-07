# noinspection PyPackageRequirements

# from utils import helpers
import asyncio
import logging
from collections import defaultdict
from datetime import datetime
from typing import Union, List, Optional

import hikari
import lightbulb
import psutil
from docker.models.containers import Container
# from OGBotPlus import OGBotPlus
from hikari import GuildChannel

from utils import sensor
from utils.servers import minecraft, source, base, docker_minecraft as mc_docker

plugin = lightbulb.Plugin("Game")

if psutil.WINDOWS:
    print("(Game Plugin) | Windows might be compatible sometimes, but is not supported as a server host.")


class ChatMessage:
    def __init__(self, chat_name, chat_id, sender_name='', text="", embeds=None, attachments=None):
        self.chat_name = chat_name
        self.chat_id = chat_id
        self.sender_name = sender_name
        self.text = text
        self.embeds = embeds
        self.attachments = attachments

    def __repr__(self):
        return f"{self.sender_name + ': ' if self.sender_name else ''}{self.text}"

    def __str__(self):
        return f"{self.sender_name + ': ' if self.sender_name else ''}{self.text}"


class ServerCoordinator:
    """Object that creates, manages, and communicates with game servers"""

    def __init__(self):
        self._game_running = asyncio.Event()
        self._chat_channels = plugin.app.chat_channels
        # self._chat_channels = plugin.app.d['config']['CHAT_CHANNELS']
        self.games = {}
        self.game_statuses = {}
        self.status_lock = asyncio.Lock()
        self.game_chat_info = {}
        self.chat_info_lock = asyncio.Lock()
        self.message_queue = asyncio.Queue()

        self._last_chat = ''
        self._last_user = ''

        pass

    @property
    def is_game_running(self):
        return self._game_running.is_set()

    @property
    def is_game_stopped(self):
        return not self._game_running.is_set()

    async def wait_until_game_running(self, delay=0):
        await self._game_running.wait()
        if delay:
            await asyncio.sleep(delay)

    # async def wait_until_game_stopped(self, delay=0):
    #     await self._game_stopped.wait()
    #     if delay:
    #         await asyncio.sleep(delay)

    @property
    def chat_channels(self) -> List[Optional[GuildChannel]]:
        result = []
        for chan in self.chat_channels:
            try:
                result.append(plugin.app.cache.get_guild_channel(chan))
            except (hikari.ForbiddenError, hikari.NotFoundError):  # this is just a guess at what it'll raise
                # TODO: Learn more logging and make this more betterer
                print(f"Couldn't find channel with id {chan}. It may have been deleted.")
                continue
        return result

    async def add_game_presence(self, game_name: str, activity: str):
        async with self.status_lock:
            self.game_statuses[game_name] = activity

    async def remove_game_presence(self, game_name: str):
        async with self.status_lock:
            self.game_statuses.pop(game_name, None)

    async def set_game_presence(self):
        status_set = False
        while True:
            if not self.game_statuses.keys():
                if status_set:
                    await plugin.app.update_presence()
                    status_set = False
                await asyncio.sleep(5)
                continue
            async with self.status_lock:
                presences = [v for k, v in self.game_statuses.items()]
            activity = hikari.Activity(name="; ".join(presences), type=0)
            try:
                await plugin.app.update_presence(activity=activity)
                status_set = True
            except Exception as e:
                print(e)
            finally:
                await asyncio.sleep(120)

    async def add_game_chat_info(self, game_name: str, info: str):
        async with self.chat_info_lock:
            self.game_chat_info[game_name] = info

    async def remove_game_chat_info(self, game_name: str):
        async with self.chat_info_lock:
            self.game_statuses.pop(game_name, None)

    async def set_game_chat_info(self):
        topic_set = False
        while True:
            try:
                if not self.game_statuses.keys():
                    if topic_set:
                        for chan in self.chat_channels:
                            await chan.edit(topic="")
                            await asyncio.sleep(1.5)
                    # await asyncio.sleep(5)
                    continue
                info = [v for k, v in self.game_chat_info.items()]
                for chan in self.chat_channels:
                    topic = "Playing: " + "; ".join(info)
                    await chan.edit(topic=topic)
                    await asyncio.sleep(1.5)
                topic_set = True
            except Exception as e:
                print(e)
            finally:
                await asyncio.sleep(320)

    # A message will always have a sending user, an identifier, and a human readable chat name
    # It can also have:
    # text: string | pretty much all messages from games will have these.
    # attachment: ??? | only messages from Discord will have these
    # embed: hikari.Embed | ^ * * * * * * ^

    async def queue_chat_messages(self, chat_identifier: str, messages: list):
        await self.message_queue.put((chat_identifier, messages))

    async def _process_messages_loop(self):
        items = []
        while True:
            while not self.message_queue.empty():
                items.append(await self.message_queue.get())
                self.message_queue.task_done()
            try:
                await self.send_chat_messages(items)
            finally:
                items = []

    async def send_chat_messages(self, items):
        # _msgs_to_be_awaited = []
        organizer = defaultdict(list)
        _last_chat = self._last_chat
        _last_user = self._last_user

        for channel in self.chat_channels:
            channel: hikari.TextableChannel
            _msg_buffer = []
            _temp_last_chat = _last_chat
            _temp_last_user = _last_user
            for messages in items:
                for message in messages:
                    if hash(channel.id) == message.chat_id:
                        break  # breaks out of a single group of messages, because they'll all be from the same game
                    if message.chat_id != _temp_last_chat:
                        if len(f'___**[{message.chat_name}]**___') + sum([len(e) for e in _msg_buffer]) > 1900:
                            organizer[message.chat_id].append(channel.send(content='\n'.join(_msg_buffer)))
                            _msg_buffer.clear()
                        _msg_buffer.append(f'___**[{message.chat_name}]**___')
                        _temp_last_chat = hash(message.chat_id)
                        pass
                    # if the sender name is baked into the message, don't render the name
                    msg_text = ''
                    if message.sender_name:
                        msg_text = message.text if _temp_last_user == message.sender_name else str(message)

                    if message.embeds or message.attachments:
                        organizer[message.chat_id].append(channel.send(content='\n'.join(_msg_buffer)))
                        _msg_buffer.clear()
                        organizer[message.chat_id].append(
                            channel.send(content=msg_text, embeds=message.embeds, attachments=message.attachments))
                        continue

                    if len(msg_text) >= 2000:
                        # do something idk
                        pass
                    if len(msg_text) + sum([len(e) for e in _msg_buffer]) > 1900:
                        organizer[message.chat_id].append(channel.send(content='\n'.join(_msg_buffer)))
                        _msg_buffer.clear()

                    _msg_buffer.append(msg_text)
            if _msg_buffer:
                organizer[channel.id].append(channel.send(content='\n'.join(_msg_buffer)))
                _msg_buffer.clear()

        for game in self.games:
            _msg_buffer = []
            _temp_last_chat = _last_chat
            _temp_last_user = _last_user
            for messages in items:
                for message in messages:
                    if game.ident == message.chat_id:
                        break  # breaks out of a single group of messages, because they'll all be from the same place
                    if message.chat_id != _temp_last_chat:
                        _msg_buffer.append(f'___**[{message.chat_name}]**___')
                    # if the sender name is baked into the message, don't render the name
                    msg_text = str(message)

                    _msg_buffer.append(msg_text)
                    if message.embeds or message.attachments:
                        # TODO: Process this!
                        pass

            if _msg_buffer:
                organizer[game.ident].append(game.send(content='\n'.join(_msg_buffer)))
                _msg_buffer.clear()

        # await asyncio.gather(*_msgs_to_be_awaited)

    # async def send_chat_to_guilds(self, messages: list, **kwargs):
    #     # TODO: Fill this out
    #     for chan in self.chat_channels:
    #         # await chan.send(msg, user_mentions=mentioned_users)
    #         pass
    #     pass
    #
    # async def send_chat_to_games(messages: list):
    #     pass


loop = None
check_server = None
get_current_status = None
ports = []
last_sender_id = 0
last_guild_id = 0
last_message_time = 0
coordinator = ServerCoordinator()


@plugin.listener(hikari.ShardReadyEvent)
async def on_start(_):
    global loop
    global check_server
    global ports
    logging.info("starting game plugin...")
    if not loop:
        loop = asyncio.get_running_loop()
        asyncio.ensure_future(coordinator.set_game_presence())
        asyncio.ensure_future(coordinator.set_game_chat_info())
    if not check_server:
        check_server = loop.create_task(server_running_loop())
    ports = plugin.app.cfg['game_port_range']


@plugin.listener(hikari.GuildMessageCreateEvent)
async def on_chat_message_in_chat_channel(event: hikari.GuildMessageCreateEvent):
    if event.author.is_bot:
        return
    elif event.channel_id in coordinator.chat_channels:
        global last_sender_id
        global last_guild_id
        global last_message_time
        if not event.message.content or len(event.message.content) < 1750:
            msg = ''
            if last_sender_id != int(event.author_id) \
                    or last_guild_id != int(event.guild_id) \
                    or int(datetime.now().timestamp()) > int(last_message_time) + 180:
                msg += f"___**[{event.author.username} ({event.get_guild().name})]**___"
            if event.message.content:
                msg += "\n" + event.message.content
            for chan in coordinator.chat_channels:
                chan: hikari.GuildTextChannel
                if chan.id != event.channel_id:
                    await chan.send(msg, user_mentions=event.message.mentions.users,
                                    attachments=event.message.attachments)
        else:
            await event.member.send("The message you sent was too long. `len(event.message.content) > 1750`")
    # TODO: update these when a chat message is sent from the game, so it doesn't look like it was sent from the game
    last_sender_id = event.author_id
    last_guild_id = event.guild_id
    last_message_time = datetime.now().timestamp()


async def server_running_loop():
    known_running_servers = []
    logging.info("Initializing server-check loop...")
    while plugin.app.is_alive:
        any_server_running = sensor.are_servers_running(ports)
        if any_server_running:
            logging.info('At least 1 server is running. Checking...')
            if not coordinator.is_game_running:
                coordinator._game_running.set()
                logging.info('set game to running')
            # print('test')
            running_servers = sensor.get_running_servers(ports)
            logging.info(f"Currently running server(s): {running_servers}")

            new_servers = [(port, server) for port, server in running_servers if
                           (isinstance(server, psutil.Process) and server.pid not in known_running_servers) or
                           (isinstance(server, Container) and server.id not in known_running_servers)]
            logging.info(f"New server(s): {new_servers}")
            if not new_servers:
                await asyncio.sleep(2)
                continue
            for port, server in new_servers:
                # print("test 2")
                data = sensor.get_game_info(server)
                logging.info(f"Got server data: {data}")
                coordinator.games[str(port)] = generate_server_object(bot=plugin.app,
                                                                      process=server,
                                                                      gameinfo=data)
                print(f"Server Status | Now Playing: {data['name']} ({port})")
                known_running_servers = []
                for _, x in running_servers:
                    if isinstance(server, psutil.Process):
                        known_running_servers.append(x.pid)
                    elif isinstance(server, Container):
                        known_running_servers.append(x.id)

        elif not any_server_running and coordinator.is_game_running:
            coordinator._game_running.clear()
        await asyncio.sleep(5)


def generate_server_object(bot, process: Union[Container, psutil.Process], gameinfo: dict) -> base.BaseServer:
    executable = gameinfo['executable'].lower()
    if isinstance(process, Container):
        process: Container
        print('test')
        if 'minecraft' in process.labels['com.docker.compose.service']:
            print('found docker minecraft')
            return mc_docker.MinecraftDockerServer(bot, process, **gameinfo)
    elif isinstance(process, psutil.Process):
        if 'srcds' in executable:
            return source.SourceServer(bot, process, **gameinfo)
        elif gameinfo['game'] == "minecraft" \
                or ('java' in executable and ('forge' in ' '.join(gameinfo['command']))
                    or 'server.jar' in ' '.join(gameinfo['command'])
                    or 'nogui' in ' '.join(gameinfo['command'])):  # words cannot describe how scuffed this is.
            return minecraft.MinecraftServer(bot, process, **gameinfo)
        # elif 'valheim_server' in executable:
        #     return valheim.ValheimServer(bot, process, **gameinfo)
        elif 'terraria' in executable:
            pass  # nyi
    else:
        print("Didn't find server... hm.")

#
# async def receive_guild_chat(messages: list, **kwargs):
#     # TODO: Fill this out
#     for chan in coordinator.chat_channels:
#         pass
#         # await chan.send(msg, user_mentions=mentioned_users)
#     pass
#
#
# async def send_game_chat(messages: list):
#     pass
