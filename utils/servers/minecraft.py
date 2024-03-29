import asyncio
import datetime
import os
import socket
import textwrap as tw
from os import path
from typing import List, Optional

import aiofiles
import hikari
import mcrcon
import psutil
import regex
from hikari.errors import ForbiddenError
from mcstatus import MinecraftServer as mc

from OGBotPlus import OGBotPlus
from utils.servers.base import BaseServer


class MinecraftServer(BaseServer):

    def __init__(self, bot: OGBotPlus, process: psutil.Process, **kwargs):
        super().__init__(bot, process, **kwargs)
        self.bot.loop.create_task(self.chat_from_game_to_guild())
        self.bot.loop.create_task(self.chat_from_guild_to_game())
        self.bot.loop.create_task(self.update_server_information())
        self.bot.loop.create_task(self.wait_for_death())
        self.motd: str = kwargs.pop('motd', "A Minecraft Server")
        self._repr = "Minecraft"

    async def _rcon_connect(self):
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

    async def _move_log(self):
        await self._rcon_connect()
        async with self.rcon_lock:
            self.rcon.command("seed")
        pass

    async def chat_from_game_to_guild(self):
        file_path = path.join(self.working_dir, "logs", "latest.log") if path.exists(
            path.join(self.working_dir, "logs", "latest.log")) else os.path.join(self.working_dir, "server.log")
        server_filter = regex.compile(
            r"INFO\]:?(?:.*tedServer\]:)? (\[[^\]]*: .*\].*|(?<=]:\s).* the game|.* has made the .*)")
        player_filter = regex.compile(r"FO\]:?(?:.*tedServer\]:)? (\[Server\].*|<.*>.*)")

        while self.proc.is_running() and self.bot.is_alive:
            try:
                await self.read_server_log(str(file_path), player_filter, server_filter)
                await self._move_log()
                await asyncio.sleep(1)
            except Exception as e:
                print(e)

    async def read_server_log(self, file_path, player_filter, server_filter):
        date = datetime.datetime.now().day
        async with aiofiles.open(file_path) as log:
            await log.seek(0, 2)
            while self.proc.is_running() and self.bot.is_alive:
                lines = await log.readlines()  # Returns instantly
                msgs = list()
                for line in lines:
                    raw_player_msg: List[Optional[str]] = regex.findall(player_filter, line)
                    raw_server_msg: List[Optional[str]] = regex.findall(server_filter, line)

                    if raw_player_msg:
                        mentioned_users, x = self.check_for_mentions(raw_player_msg[0])
                        msgs.append(x)
                        # pass
                    elif raw_server_msg:
                        msgs.append(f'`{raw_server_msg[0].rstrip()}`')
                    else:
                        continue
                if msgs:
                    x = "\n".join(msgs)
                    for chan in self.bot.chat_channels_obj:
                        chan: hikari.GuildTextChannel
                        await chan.send(x, user_mentions=mentioned_users)
                for msg in msgs:
                    self.bot.bprint(f"{self._repr} | {''.join(msg)}")

                if date != datetime.datetime.now().day:
                    break
                await asyncio.sleep(.75)

    def remove_nestings(self, iterable):
        output = []
        for i in iterable:
            if type(i) == list:
                output.extend(self.remove_nestings(i))
            else:
                output.append(i)
        return output

    async def chat_from_guild_to_game(self):
        while self.proc.is_running() and self.bot.is_alive:
            try:
                msg: hikari.Message = await self.bot.wait_for(hikari.events.GuildMessageCreateEvent, predicate=self.is_chat_channel,
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

    async def update_server_information(self):
        tries = 1
        server = mc.lookup(f"{self.ip}:{self.port}")
        while self.proc.is_running() and self.bot.is_alive:
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
