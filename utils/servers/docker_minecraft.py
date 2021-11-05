import asyncio
import datetime
import socket
import textwrap as tw
from typing import List, Tuple, Optional

import hikari
import lightbulb
import mcrcon
import regex
from docker.models.containers import Container
from hikari.errors import ForbiddenError
from mcstatus import MinecraftServer as mc

from OGBotPlus import OGBotPlus
from utils.servers.base import BaseServer


class MinecraftDockerServer(BaseServer):

    def __init__(self, bot: OGBotPlus, process: Container, **kwargs):
        bot.bprint("initialized")
        super().__init__(bot, process, **kwargs)
        bot.bprint("super called")
        self.bot.loop.create_task(self.chat_from_game_to_guild())
        self.bot.loop.create_task(self.chat_from_guild_to_game())
        self.bot.loop.create_task(self.update_server_information())
        self.bot.loop.create_task(self.wait_for_death())
        bot.bprint("taskes created")
        self.motd: str = kwargs.pop('motd', "A Dockerized Minecraft Server")
        self._repr = "Minecraft In Docker"

    async def _rcon_connect(self):
        self.bot.bprint("rcon_connect")
        if not self.rcon:
            self.rcon = mcrcon.MCRcon(self.ip, self.password, port=self.rcon_port)
        try:
            connection_length = (datetime.datetime.now() - self.last_reconnect)
            async with self.rcon_lock:
                if connection_length.total_seconds() >= 600:
                    try:
                        self.rcon.connect()
                        self.last_reconnect = datetime.datetime.now()
                    except mcrcon.MCRconException as e:
                        print(e)
        except Exception as e:
            print(e)
            pass

    # async def _move_log(self):
    #     await self._rcon_connect()
    #     async with self.rcon_lock:
    #         self.rcon.command("seed")
    #     pass

    def is_running(self) -> bool:
        # self.bot.bprint("is_running")
        self.proc.reload()
        if self.proc.status == 'running':
            return True
        else:
            return False

    async def chat_from_game_to_guild(self):
        self.bot.bprint("chat_from_game_to_guild")
        # file_path = path.join(self.working_dir, "logs", "latest.log") if path.exists(
        #     path.join(self.working_dir, "logs", "latest.log")) else os.path.join(self.working_dir, "server.log")

        while self.is_running() and self.bot.is_alive:
            try:
                await self.read_server_log()
                # await self.read_server_log(str(file_path), player_filter, server_filter)
                # await self._move_log()
                await asyncio.sleep(1)
            except Exception as e:
                print(e)
                await asyncio.sleep(.1)

    # async def read_server_log(self, file_path, player_filter, server_filter):
    #     date = datetime.datetime.now().day
    #     async with aiofiles.open(file_path) as log:
    #         await log.seek(0, 2)
    #         while self.is_running() and self.bot.is_alive:
    #             lines = await log.readlines()  # Returns instantly
    #             msgs = list()
    #             for line in lines:
    #                 raw_player_msg: List[Optional[str]] = regex.findall(player_filter, line)
    #                 raw_server_msg: List[Optional[str]] = regex.findall(server_filter, line)
    #
    #                 if raw_player_msg:
    #                     mentioned_users, x = self.check_for_mentions(raw_player_msg[0])
    #                     msgs.append(x)
    #                     # pass
    #                 elif raw_server_msg:
    #                     msgs.append(f'`{raw_server_msg[0].rstrip()}`')
    #                 else:
    #                     continue
    #             if msgs:
    #                 x = "\n".join(msgs)
    #                 for chan in self.bot.chat_channels_obj:
    #                     chan: hikari.GuildTextChannel
    #                     await chan.send(x, user_mentions=mentioned_users)
    #             for msg in msgs:
    #                 self.bot.bprint(f"{self._repr} | {''.join(msg)}")
    #
    #             if date != datetime.datetime.now().day:
    #                 break
    #             await asyncio.sleep(.75)

    async def read_server_log(self):
        print('reading_server_log')
        watcher = await asyncio.create_subprocess_shell(cmd=f"docker logs -f --tail 0 --since 0m {self.proc.id}",
                                                        stdout=asyncio.subprocess.PIPE)
        print(type(watcher.stdout))
        print('created watcher')
        while self.is_running() and self.bot.is_alive:
            await asyncio.wait([self._read_stream(watcher.stdout, self.process_server_messages)])
        pass

    @staticmethod
    async def _read_stream(stream: asyncio.streams.StreamReader, cb):
        lines = []
        while True:
            try:
                line = await asyncio.wait_for(stream.readuntil(), timeout=2)
                lines.append(line.decode('utf-8'))
            except asyncio.exceptions.TimeoutError:
                if lines:
                    await cb(lines)
                    lines = []
                    await asyncio.sleep(1)

    async def process_server_messages(self, out):
        server_filter = regex.compile(
            r"INFO\]:?(?:.*tedServer\]:)? (\[[^\]]*: .*\].*|(?<=]:\s).* the game|.* has made the .*)")
        player_filter = regex.compile(r"FO\]:?(?:.*tedServer\]:)? (\[Server\].*|<.*>.*)")
        msgs = []
        mentioned_users = []
        for line in out:
            # print(type(line))
            # print(line)
            raw_player_msg: List[Optional[str]] = regex.findall(player_filter, line)
            raw_server_msg: List[Optional[str]] = regex.findall(server_filter, line)

            if raw_player_msg:
                # mentioned_users, x = self.check_for_mentions(raw_player_msg[0])
                ret = self.check_for_mentions(raw_player_msg[0])
                mentioned_users += ret[0]
                x = ret[1]
                msgs.append((x, mentioned_users))
                # pass
            elif raw_server_msg:
                msgs.append((f'`{raw_server_msg[0].rstrip()}`', None))
            else:
                continue
        if msgs:
            x = "\n".join(list(zip(*msgs))[0])
            for chan in self.bot.chat_channels_obj:
                await chan.send(x, user_mentions=mentioned_users)
        for msg in msgs:
            self.bot.bprint(f"{self._repr} | {''.join(msg)}")

    def check_for_mentions(self, message: str) -> Tuple[List[hikari.snowflakes.Snowflakeish], str]:
        indexes: List[int] = [m.start() for m in regex.finditer('@', message)]
        mentioned_members = []
        for index in indexes:
            try:
                mention = message[index + 1:]
                for chan in self.bot.chat_channels_obj:
                    for ind in range(0, min(len(mention) + 1, 32)):
                        member = lightbulb.utils.find(self.bot.cache.get_guild(chan.guild_id).get_members().values(),
                                                      lambda m: m.username == mention[:ind] or
                                                                m.nickname == mention[:ind])
                        if member:
                            mentioned_members.append(member)
                            message = message.replace("@" + mention[:ind], f"<@{member.id}>")
                            break

            except Exception as e:
                self.bot.bprint("ERROR | Server2Guild Mentions Exception caught: " + str(e))
                pass
        return mentioned_members, message

    def remove_nestings(self, iterable):
        output = []
        for i in iterable:
            if type(i) == list:
                output.extend(self.remove_nestings(i))
            else:
                output.append(i)
        return output

    async def chat_from_guild_to_game(self):
        while self.is_running() and self.bot.is_alive:
            try:
                msg = await self.bot.wait_for(hikari.events.GuildMessageCreateEvent, predicate=self.is_chat_channel,
                                              timeout=5)
            except asyncio.exceptions.TimeoutError:
                continue
            try:
                if not hasattr(msg, 'author') or (hasattr(msg, 'author') and msg.author.is_bot):
                    pass
                elif msg.content:
                    await self._rcon_connect()
                    content = regex.sub(r'<(:\w+:)\d+>', r'\1', msg.content).split('\n')  # split on msg newlines
                    long = False
                    for index, line in enumerate(content):
                        data = f"§9§l{msg.author.username}§r: {line}"
                        if len(data) >= 100:
                            # if length of prefix + msg > 100 chars...
                            if index == 0:
                                # ...and current line is the first line, split the line, adding a prefix...
                                content[index] = tw.wrap(line, 90, initial_indent=f"§9§l{msg.author.username}§r: ")
                            else:
                                # ...else, just split the line, without the prefix.
                                content[index] = tw.wrap(line, 90)
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

                    self.bot.bprint(f"Discord | <{msg.author.username}>: {' '.join(content)}")
            except mcrcon.MCRconException as e:
                print(e)
                await asyncio.sleep(2)
            except socket.error as e:
                print(e)
                for chan in self.bot.chat_channels_obj:
                    if chan.channel_id == msg.channel_id:
                        await chan.send("Message failed to send; the bot is broken, tag Evan",
                                        delete_after=10)
                continue
            except Exception as e:
                self.bot.bprint("guild2server catchall:")
                print(type(e))
                print(e)

    async def wait_for_death(self):
        print('waiting for the server to DIE')
        while True:
            self.proc.reload()
            if self.proc.status == 'running':
                await asyncio.sleep(5)
            else:
                await asyncio.sleep(2)
                break
        self.teardown()

    async def update_server_information(self):
        tries = 1
        server = mc.lookup(f"{self.ip}:{self.port}")
        while self.is_running() and self.bot.is_alive:
            failed = False
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
                cur_status = f"Minecraft {version} {player_count} {'[' if names else ''}{', '.join(names)}{']' if names else ''}"
                await self.bot.add_game_chat_info(self.name, cur_status)
                await self.bot.add_game_presence(self.name, f'{self._repr} {version} {mod_count} {player_count}')
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
                self.bot.bprint("Bot lacks permissions to edit channels. (hikari.ForbiddenError)")
                pass
            except NameError:
                pass
            except Exception as e:
                self.bot.bprint(f"Failed with Exception {e}")
                failed = True
                pass
            finally:
                await asyncio.sleep(30)
