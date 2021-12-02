# noinspection PyPackageRequirements

# from utils import helpers
import asyncio
import logging
from typing import Union

import hikari
import lightbulb
import psutil
from docker.models.containers import Container

# from OGBotPlus import OGBotPlus
from utils import sensor
from utils.servers import minecraft, valheim, source, base, docker_minecraft as mc_docker

plugin = lightbulb.Plugin("Game")

if psutil.WINDOWS:
    print("(Game Plugin) | Windows might be compatible sometimes, but is not supported as a server host.")

loop = None
check_server = None
get_current_status = None
ports = []


@plugin.listener(hikari.ShardReadyEvent)
async def on_start(_):
    global loop
    global check_server
    global ports
    logging.info("starting game plugin...")
    if not loop:
        loop = asyncio.get_running_loop()
        asyncio.ensure_future(plugin.app.set_game_presence())
        asyncio.ensure_future(plugin.app.set_game_chat_info())
    if not check_server:
        check_server = loop.create_task(server_running_loop())
    ports = plugin.app.cfg['game_port_range']


@plugin.listener(hikari.GuildMessageCreateEvent)
async def on_chat_message_in_chat_channel(self, event: hikari.GuildMessageCreateEvent):
    if event.author.is_bot:
        return
    if event.channel_id in plugin.app.chat_channels:
        if len(event.message.content) < 1750:
            for chan in plugin.app.chat_channels_obj:
                chan: hikari.GuildTextChannel
                if chan.id != event.channel_id:
                    await chan.send(
                        f"`{event.author.username} ({event.get_guild().name})`\n{event.message.content}",
                        user_mentions=event.message.mentions.users, attachments=event.message.attachments)
        else:
            await event.member.send("The message you sent was too long. `len(event.message.content) > 1750`")


async def server_running_loop():
    known_running_servers = []
    logging.info("Initializing server-check loop...")
    while plugin.app.is_alive:
        any_server_running = sensor.are_servers_running(ports)
        if any_server_running:
            logging.info('At least 1 server is running. Checking...')
            if not plugin.app.is_game_running:
                plugin.app._game_stopped.clear()
                plugin.app._game_running.set()
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
                plugin.app.games[str(port)] = generate_server_object(bot=plugin.app,
                                                                     process=server,
                                                                     gameinfo=data)
                plugin.app.bprint(f"Server Status | Now Playing: {data['name']} ({port})")
                known_running_servers = []
                for _, x in running_servers:
                    if isinstance(server, psutil.Process):
                        known_running_servers.append(x.pid)
                    elif isinstance(server, Container):
                        known_running_servers.append(x.id)

        elif not any_server_running and plugin.app.is_game_running:
            plugin.app._game_running.clear()
            plugin.app._game_stopped.set()
        await asyncio.sleep(5)


def generate_server_object(bot, process: Union[Container, psutil.Process], gameinfo: dict) -> base.BaseServer:
    executable = gameinfo['executable'].lower()
    if isinstance(process, Container):
        process: Container
        print('test')
        if 'minecraft' in process.labels['com.docker.compose.service']:
            print('asdfasd')
            return mc_docker.MinecraftDockerServer(bot, process, **gameinfo)
    elif isinstance(process, psutil.Process):
        if 'srcds' in executable:
            return source.SourceServer(bot, process, **gameinfo)
        elif gameinfo['game'] == "minecraft" \
                or ('java' in executable and ('forge' in ' '.join(gameinfo['command']))
                    or 'server.jar' in ' '.join(gameinfo['command'])
                    or 'nogui' in ' '.join(gameinfo['command'])):  # words cannot describe how scuffed this is.
            return minecraft.MinecraftServer(bot, process, **gameinfo)
        elif 'valheim_server' in executable:
            return valheim.ValheimServer(bot, process, **gameinfo)
        elif 'terraria' in executable:
            pass  # nyi
    else:
        print("Didn't find server... hm.")
