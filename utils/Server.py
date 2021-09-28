import asyncio
import datetime
import os
import socket
import textwrap as tw
from os import path

import a2s
import aiofiles
import hikari
import mcrcon
import psutil
import regex
import valve.rcon as valvercon
import valve.source
from hikari import ForbiddenError
from mcstatus import MinecraftServer as mc

valvercon.RCONMessage.ENCODING = "utf-8"


class Server:
    def __init__(self, bot, process, *args, **kwargs):
        self.bot = bot
        self.proc = process
        self.name = kwargs.pop('name', 'a game')
        self.ip = kwargs.pop('ip', '127.0.0.1')
        self.port = kwargs.pop('port', '22222')
        self.password = kwargs.pop('rcon_password') if kwargs.get('rcon_password') else kwargs.pop(
            'rcon') if kwargs.get('rcon') else self.bot.cfg["default_rcon_password"]
        self.working_dir = kwargs.pop('folder', '')
        self._repr = "a game"

        self.rcon_port = kwargs.pop('rcon_port', 22232)
        self.rcon = None
        self.rcon_lock = asyncio.Lock()
        self.last_reconnect = datetime.datetime(1, 1, 1)

        if self.__class__.__name__ == 'Server':
            self.bot.loop.create_task(self.update_server_information())

        # self.bot.loop.create_task(self.chat_from_game_to_guild())
        # self.bot.loop.create_task(self.chat_from_guild_to_game())

    def __repr__(self):
        return self._repr

    def is_running(self) -> bool:
        return self.proc.is_running()

    async def _log_loop(self):
        pass

    async def chat_from_game_to_guild(self):
        pass

    async def chat_from_guild_to_game(self):
        pass

    async def update_server_information(self):
        print("server")
        await self.bot.set_bot_status(self.name, "", "")

    async def sleep_with_backoff(self, tries, wait_time=5):
        await asyncio.sleep(wait_time * tries)
        if self.bot.debug:
            self.bot.bprint("sleep_with_backoff ~ Done waiting for backoff")

    @property
    def status(self) -> psutil.Process:
        return self.proc

    @property
    def players(self) -> int:
        return 0

    def is_chat_channel(self, m) -> bool:
        return m.channel == self.bot.chat_channel


class A2SCompatibleServer(Server):
    def __init__(self, bot, process, *args, **kwargs):
        super().__init__(bot, process, *args, **kwargs)
        self._repr = "A2S-Compatible Server"
        self.readable_name = kwargs.setdefault('name', 'A2S-Compatible Server')

    async def update_server_information(self):
        while self.proc.is_running() and not self.bot.is_closed():
            try:
                info = await a2s.ainfo((self.ip, 22223))

                cur_p = info.player_count
                chat_status = f"Playing: {self.readable_name} | ({cur_p} player{'s' if cur_p != 1 else ''})"

                await self.bot.chat_channel.edit(topic=chat_status)
                await self.bot.set_bot_status(self.readable_name,
                                              f"({cur_p} player{'s' if cur_p != 1 else ''} online)",
                                              f"CPU: {self.proc.cpu_percent(interval=0.1)}% | Mem: {round(self.proc.memory_percent(), 2)}%")
            except ForbiddenError:
                print("Bot lacks permission to edit channels. (discord.Forbidden)")
            except valve.source.NoResponseError:
                print("No Response from server before timeout (NoResponseError)")
            except Exception as e:
                print(f"Error: {e} {type(e)}")
            await asyncio.sleep(30)


class MinecraftServer(Server):

    def __init__(self, bot, process, *args, **kwargs):
        super().__init__(bot, process, *args, **kwargs)
        self.bot.loop.create_task(self.chat_from_game_to_guild())
        self.bot.loop.create_task(self.chat_from_guild_to_game())
        self.bot.loop.create_task(self.update_server_information())
        self.motd = kwargs.pop('motd', "A Minecraft Server")
        self._repr = "Minecraft"

    async def _rcon_connect(self):
        if not self.rcon:
            self.rcon = mcrcon.MCRcon(self.ip, self.password, port=self.rcon_port)
        try:
            time_sec = (datetime.datetime.now() - self.last_reconnect)
            async with self.rcon_lock:
                if time_sec.total_seconds() >= 600:
                    try:
                        self.rcon.connect()
                        self.last_reconnect = datetime.datetime.now()
                    except mcrcon.MCRconException as e:
                        print(e)
        except Exception as e:
            print(e)
            pass

    async def _move_alog(self):
        await self._rcon_connect()
        async with self.rcon_lock:
            self.rcon.command("seed")
        pass

    async def chat_from_game_to_guild(self):
        fpath = path.join(self.working_dir, "logs", "latest.log") if path.exists(
            path.join(self.working_dir, "logs", "latest.log")) else os.path.join(self.working_dir, "server.log")
        server_filter = regex.compile(
            r"INFO\]:?(?:.*tedServer\]:)? (\[[^\]]*: .*\].*|(?<=]:\s).* the game|.* has made the .*)")
        player_filter = regex.compile(r"FO\]:?(?:.*tedServer\]:)? (\[Server\].*|<.*>.*)")

        while self.proc.is_running() and not self.bot.is_closed():
            try:
                await self.read_server_log(str(fpath), player_filter, server_filter)
                await self._move_alog()
                await asyncio.sleep(1)
            except Exception as e:
                print(e)

    async def read_server_log(self, fpath, player_filter, server_filter):
        date = datetime.datetime.now().day
        async with aiofiles.open(fpath) as log:
            await log.seek(0, 2)
            while self.proc.is_running() and not self.bot.is_closed():
                lines = await log.readlines()  # Returns instantly
                msgs = list()
                for line in lines:
                    raw_playermsg = regex.findall(player_filter, line)
                    raw_servermsg = regex.findall(server_filter, line)

                    if raw_playermsg:
                        pass
                        # x = self.check_for_mentions(raw_playermsg)
                        # msgs.append(x)
                    elif raw_servermsg:
                        msgs.append(f'`{raw_servermsg[0].rstrip()}`')
                    else:
                        continue
                if msgs:
                    x = "\n".join(msgs)
                    await self.bot.chat_channel.send(f'{x}')
                for msg in msgs:
                    self.bot.bprint(f"{self.bot.game} | {''.join(msg)}")

                if date != datetime.datetime.now().day:
                    break
                await asyncio.sleep(.75)

    def check_for_mentions(self, raw_playermsg):
        pass
    # def check_for_mentions(self, raw_playermsg) -> str:
    #     message = raw_playermsg[0]
    #     indexes = [m.start() for m in regex.finditer('@', message)]
    #     if indexes:
    #         try:
    #             for index in indexes:
    #                 mention = message[index + 1:]
    #                 length = len(mention) + 1
    #                 for ind in range(0, length):
    #                     member = discord.utils.find(lambda m: m.name == mention[:ind] or m.nick == mention[:ind],
    #                                                 self.bot.chat_channel.members)
    #                     if member:
    #                         message = message.replace("@" + mention[:ind], f"<@{member.id}>")
    #                         break
    #         except Exception as e:
    #             self.bot.bprint("ERROR | Server2Guild Mentions Exception caught: " + str(e))
    #             pass
    #     return message

    def remove_nestings(self, l):
        output = []
        for i in l:
            if type(i) == list:
                output.extend(self.remove_nestings(i))
            else:
                output.append(i)
        return output

    async def chat_from_guild_to_game(self):
        while self.proc.is_running() and not self.bot.is_closed():
            try:
                msg = await self.bot.wait_for('message', check=self.is_chat_channel, timeout=5)
                if not hasattr(msg, 'author') or (hasattr(msg, 'author') and msg.author.bot):
                    pass
                elif msg.clean_content:
                    await self._rcon_connect()
                    content = regex.sub(r'<(:\w+:)\d+>', r'\1', msg.clean_content).split('\n')  # split on msg newlines
                    long = False
                    for index, line in enumerate(content):
                        data = f"§9§l{msg.author.name}§r: {line}"
                        if len(data) >= 100:
                            # if length of prefix + msg > 100 chars...
                            if index == 0:
                                # ...and current line is the first line, split the line, adding a prefix...
                                content[index] = tw.wrap(line, width=90, initial_indent=f"§9§l{msg.author.name}§r: ")
                            else:
                                # ...else, just split the line, without the prefix.
                                content[index] = tw.wrap(line, width=90)
                            long = True
                        elif index == 0:
                            # ...else, if less than 100 chars and on the first line, set to data variable
                            content[index] = data
                        else:
                            # ...else, just return the line
                            content[index] = line
                    if long:
                        # flatten list into a single layer
                        content = self.remove_nestings(content)

                    async with self.rcon_lock:
                        for line in content:
                            self.rcon.command(f"say {line}")

                    self.bot.bprint(f"Discord | <{msg.author.name}>: {' '.join(content)}")
            except mcrcon.MCRconException as e:
                print(e)
                await asyncio.sleep(2)
            except socket.error as e:
                print(e)
                await self.bot.chat_channel.send("Message failed to send; the bot is broken, tag Evan", delete_after=10)
                continue
            except asyncio.exceptions.TimeoutError:
                pass
            except Exception as e:
                self.bot.bprint("guild2server catchall:")
                print(type(e))
                print(e)

    async def update_server_information(self):
        tries = 1
        server = mc.lookup("localhost:22222")
        failed = False
        while self.proc.is_running() and not self.bot.is_closed():
            try:
                await asyncio.sleep(10)
                stats = server.status()
                version, online, max_p = stats.version.name, stats.players.online, stats.players.max
                names = []
                if 'sample' in stats.raw['players']:
                    for x in stats.raw['players']['sample']:
                        names.append(x['name'])
                    names.sort()
                if 'modinfo' in stats.raw:
                    mod_count = f"{len(stats.raw['modinfo']['modList'])} mods installed"
                else:
                    mod_count = 'Vanilla'
                if failed:
                    stats = server.query()
                    version, online, max_p = stats.software.version, stats.players.online, stats.players.max
                player_count = f"({online}/{max_p} players)" if not failed else ""
                cur_status = f"Playing: Minecraft {version} {player_count}\n{'[' if names else ''}{', '.join(names)}{']' if names else ''}"
                await self.bot.chat_channel.edit(topic=cur_status)
                # await self.bot.set_bot_status(f'{self.bot.game} {version}', mod_count, player_count)
                await self.bot.update_activity(f'{self.bot.game} {version} {mod_count} {player_count}')
            except BrokenPipeError:
                self.bot.bprint("Server running a MC version <1.7, or is still starting. (BrokenPipeError)")
                await self.sleep_with_backoff(tries)
                tries += 1
                pass
            except ConnectionRefusedError:
                self.bot.bprint("Server running on incorrect port. (ConnectionRefusedError)")
                break
            except ConnectionResetError:
                self.bot.bprint("Connection to server was reset by peer. (ConnectionResetError)")
                failed = True
                pass
            except ConnectionError:
                self.bot.bprint("General Connection Error. (ConnectionError)")
            except socket.timeout:
                self.bot.bprint("Server not responding. (socket.timeout)")
                failed = True
            except ForbiddenError:
                self.bot.bprint("Bot lacks permissions to edit channels. (discord.Forbidden)")
                pass
            except NameError:
                pass
            except Exception as e:
                self.bot.bprint(f"Failed with Exception {e}")
                failed = True
                pass
            finally:
                await asyncio.sleep(30)


class ValheimServer(A2SCompatibleServer):
    def __init__(self, bot, process: psutil.Process, *args, **kwargs):
        super().__init__(bot, process, *args, **kwargs)
        self.game = kwargs.pop('game', 'vhserver')
        self.bot.loop.create_task(self.chat_from_game_to_guild())
        self.bot.loop.create_task(self.chat_from_guild_to_game())
        self.bot.loop.create_task(self.update_server_information())
        self.log = list()
        self.log_lock = asyncio.Lock()
        self.bot.loop.create_task(self._log_loop())
        self._repr = "Valheim"
        self.readable_name = kwargs.setdefault('name', 'Valheim Server')

        self.logs = kwargs.pop('logs')

    async def chat_from_game_to_guild(self):
        fpath = path.join(self.logs, "console", self.game + "-console.log")

        server_filter = regex.compile(r"(.{1,15}) ((?:has (?:left|joined)|died))")
        chat_filter = regex.compile(r"(?<=Message) \: (Shout|Normal) ([\w\d\s]{1,15}): (.*)$")

        while self.proc.is_running() and not self.bot.is_closed():
            try:
                await self.read_server_log(str(fpath), chat_filter, server_filter)
            except Exception as e:
                print(type(e))
                print(e)

    async def read_server_log(self, fpath, chat_filter, server_filter):
        async with aiofiles.open(fpath) as log:
            await log.seek(0, 2)
            while self.proc.is_running() and not self.bot.is_closed():
                lines = await log.readlines()  # Returns instantly
                msgs = []
                print(msgs)
                for line in lines:
                    raw_playermsg = regex.findall(chat_filter, line)
                    raw_servermsg = regex.findall(server_filter, line)

                    if raw_playermsg:
                        # x = self.check_for_mentions(raw_playermsg)
                        if raw_playermsg[0][1] == "RCON":
                            continue
                        if "I have arrived" in raw_playermsg[0][2]:
                            continue

                        if raw_playermsg[0][0] == "Shout":
                            msgs.append(f"{raw_playermsg[0][1]} shouted {raw_playermsg[0][2]}")
                        elif raw_playermsg[0] == "Normal":
                            msgs.append(f"{raw_playermsg[0][1]} said {raw_playermsg[0][2]}")
                        msgs.append(x)
                    elif raw_servermsg:
                        msgs.append(f'`{" ".join(raw_servermsg[0])}`')
                    else:
                        continue
                if msgs:
                    x = "\n".join(msgs)
                    await self.bot.chat_channel.send(f'{x}')
                for msg in msgs:
                    self.bot.bprint(f"{self.bot.game} | {''.join(msg)}")
                await asyncio.sleep(.75)

    def check_for_mentions(self, raw_playermsg):
        pass
    # def check_for_mentions(self, raw_playermsg) -> str:
    #     message = raw_playermsg[0]
    #     indexes = [m.start() for m in regex.finditer('@', message)]
    #     if indexes:
    #         try:
    #             for index in indexes:
    #                 mention = message[index + 1:]
    #                 length = len(mention) + 1
    #                 for ind in range(0, length):
    #                     member = discord.utils.find(lambda m: m.name == mention[:ind] or m.nick == mention[:ind],
    #                                                 self.bot.chat_channel.members)
    #                     if member:
    #                         message = message.replace("@" + mention[:ind], f"<@{member.id}>")
    #                         break
    #         except Exception as e:
    #             self.bot.bprint("ERROR | Server2Guild Mentions Exception caught: " + str(e))
    #             pass
    #     return message

    async def chat_from_guild_to_game(self):
        with valvercon.RCON(('127.0.0.1', 22224), self.password) as rcon:
            while self.proc.is_running() and not self.bot.is_closed():
                try:
                    msg = await self.bot.wait_for('message', check=self.is_chat_channel, timeout=5)
                    if not hasattr(msg, 'author') or (hasattr(msg, 'author') and msg.author.bot):
                        pass
                    elif msg.clean_content:
                        rcon(f"say {msg.author.name}: {msg.clean_content}")
                        self.bot.bprint(f"Discord | <{msg.author.name}>: {msg.clean_content}")
                    if msg.attachments:
                        rcon.command(f"say {msg.author.name}: Image {msg.attachments[0]['filename']}")
                        self.bot.bprint(f"Discord | {msg.author.name}: Image {msg.attachments[0]['filename']}")
                except asyncio.exceptions.TimeoutError:
                    pass
                except Exception as e:
                    print(f"Caught Unexpected {type(e)}: ({str(e)}) (Source Server Guild2Game)")


class SourceServer(A2SCompatibleServer):
    def __init__(self, bot, process: psutil.Process, *args, **kwargs):
        super().__init__(bot, process, *args, **kwargs)
        self.bot.loop.create_task(self.chat_from_game_to_guild())
        self.bot.loop.create_task(self.chat_from_guild_to_game())
        self.bot.loop.create_task(self.update_server_information())
        self.log = list()
        self.log_lock = asyncio.Lock()
        self.bot.loop.create_task(self._log_loop())
        self._repr = "Source"
        self.readable_name = kwargs.setdefault('name', 'Source Server')

    async def _log_loop(self):
        port = 22242

        transport, protocol = await self.bot.loop.create_datagram_endpoint(
            lambda: SrcdsLoggingProtocol(self.bot.loop.create_task, self._log_callback),
            local_addr=(self.bot.cfg["local_ip"], port))

        try:
            await self.bot.wait_until_game_stopped()
        finally:
            transport.close()

    async def _log_callback(self, message):
        async with self.log_lock:
            self.log.append(message)

    async def chat_from_game_to_guild(self):
        connections = regex.compile(
            r"""(?<=: ")([\w\s]+)(<\d><(?:STEAM_0:\d:\d+|\[U:\d:\d+\])><.*>)" (?:((?:dis)?connected),? (?|address "(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}:\d{2,5})|(\(reason ".+"?)))""")
        chat = regex.compile(
            r"""(?<=: ")([\w\s]+)(?:<\d+><(?:STEAM_0:\d:\d+|Console|\[U:\d:\d+\])><.*>)" (|say|say_team) "(?!\|D> )(.*)\"""")
        while self.bot.is_game_running:
            try:
                lines = []
                async with self.log_lock:
                    if self.log:
                        lines = self.log
                        self.log = []
                msgs = list()
                for line in lines:
                    raw_connectionmsg = connections.findall(line)
                    raw_chatmsg = chat.findall(line)
                    print('DEBUG: Chat Message: ', *raw_chatmsg) if self.bot.debug else False
                    print('DEBUG: Connection Message: ', *raw_connectionmsg) if self.bot.debug else False

                    if raw_chatmsg:
                        msgs.append(
                            f"{'[TEAM] ' if raw_chatmsg[0][1] == 'say_team' else ''} *[{raw_chatmsg[0][0]}]*: {raw_chatmsg[0][2]}")
                    elif raw_connectionmsg:
                        msgs.append(f"`{' '.join(raw_connectionmsg[0])}`")
                    else:
                        continue
                print('DEBUG: list `msgs`: ', *msgs) if self.bot.debug else False
                if msgs:
                    x = "\n".join(msgs)
                    await self.bot.chat_channel.send(f'{x}')
                for msg in msgs:
                    self.bot.bprint(f"{self.bot.game} | {''.join(msg)}")
                continue
            except Exception as e:
                print(f"Caught Unexpected {type(e)}: ({str(e)}) (Source Server Game2Guild)")
            finally:
                await asyncio.sleep(.75)

    async def chat_from_guild_to_game(self):
        with valvercon.RCON((self.bot.cfg["local_ip"], 22222), self.password) as rcon:
            while self.proc.is_running() and not self.bot.is_closed():
                try:
                    msg = await self.bot.wait_for('message', check=self.is_chat_channel, timeout=5)
                    if not hasattr(msg, 'author') or (hasattr(msg, 'author') and msg.author.bot):
                        pass
                    elif msg.clean_content:
                        i = len(msg.author.name)
                        # if message is longer than 200-some characters
                        if len(msg.clean_content) > 230 - i:
                            wrapped = tw.wrap(msg.clean_content, width=230 - i,
                                              initial_indent=f"{msg.author.name}: ")
                            for wrapped_line in wrapped:
                                rcon(f"say |D> {wrapped_line}")
                        # elif shorter than 200-some characters
                        else:
                            rcon(f"say |D> {msg.author.name}: {msg.clean_content}")
                        self.bot.bprint(f"Discord | <{msg.author.name}>: {msg.clean_content}")
                    if msg.attachments:
                        rcon.command(f"say |D> {msg.author.name}: Image {msg.attachments[0]['filename']}")
                        self.bot.bprint(
                            f"Discord | {msg.author.name}: Image {msg.attachments[0]['filename']}")
                except asyncio.exceptions.TimeoutError:
                    pass
                except Exception as e:
                    print(f"Caught Unexpected {type(e)}: ({str(e)}) (Source Server Guild2Game)")

    async def update_server_information(self):
        while self.proc.is_running() and not self.bot.is_closed():
            try:
                info = a2s.info((self.bot.cfg["local_ip"], 22222))

                mode = info.game
                cur_map = info.map
                cur_p = info.player_count
                max_p = info.max_players
                cur_status = f"Playing: {self.readable_name} - {mode} on map {cur_map} ({cur_p}/{max_p} players)"

                await self.bot.chat_channel.edit(topic=cur_status)
                await self.bot.update_activity()
                # await self.bot.set_bot_status(self.readable_name, f"{mode} on {cur_map} ({cur_p}/{max_p})",
                #                               f"CPU: {self.proc.cpu_percent()}% | Mem: {round(self.proc.memory_percent(), 2)}%")
            except ForbiddenError:
                print("Bot lacks permission to edit channels. (discord.Forbidden)")
            except valve.source.NoResponseError:
                print("No Response from server before timeout (NoResponseError)")
            except Exception as e:
                print(f"Error: {e} {type(e)}")
            await asyncio.sleep(30)


def generate_server_object(bot, process, gameinfo: dict) -> Server:
    if 'java' in gameinfo['executable'].lower() and (
            'forge' in ' '.join(gameinfo['command'])
            or 'server.jar' in ' '.join(gameinfo['command'])
            or gameinfo['game'] == "minecraft"
            or 'nogui' in ' '.join(gameinfo['command'])):  # words cannot describe how scuffed this is.
        print("Found Minecraft")
        return MinecraftServer(bot, process, **gameinfo)
    elif 'srcds' in gameinfo['executable'].lower():
        return SourceServer(bot, process, **gameinfo)
    elif 'valheim_server' in gameinfo['executable'].lower():
        return ValheimServer(bot, process, **gameinfo)
    else:
        print("Didn't find server... hm.")


class SrcdsLoggingProtocol(asyncio.DatagramProtocol):

    def __init__(self, cb1, cb2):
        self.callback1 = cb1
        self.callback2 = cb2

    def connection_made(self, transport):
        print("Connected to Server")
        # noinspection PyAttributeOutsideInit
        self.transport = transport

    def datagram_received(self, packet, addr):
        message = self.parse(packet)
        self.callback1(self.callback2(message))

    @staticmethod
    def parse(packet: bytes):
        packet_len = len(packet)

        if packet_len < 7:
            raise Exception("Packet is too short")

        for i in range(4):
            if packet[i] != int(0xFF):
                raise Exception('invalid header value')

        if packet[packet_len - 1] != int(0x00):
            raise Exception('invalid footer value')

        ptype, offset, footer = packet[4], 5, 2

        if packet[packet_len - 2] != int(0x0a):
            footer = 1

        if ptype != int(0x52):
            raise Exception('invalid packet type ' + hex(ptype))

        message = packet[offset:(packet_len - footer)]

        return message.decode('utf-8').strip()
