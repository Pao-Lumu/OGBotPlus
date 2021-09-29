from utils.servers.a2s import A2SCompatibleServer
import psutil
import asyncio
import a2s
import regex
from hikari.errors import ForbiddenError
from hikari.events import GuildMessageCreateEvent
import textwrap as tw
import valve.rcon as valvercon

valvercon.RCONMessage.ENCODING = "utf-8"


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
                    # print('DEBUG: Chat Message: ', *raw_chatmsg) if self.bot.debug else False
                    # print('DEBUG: Connection Message: ', *raw_connectionmsg) if self.bot.debug else False

                    if raw_chatmsg:
                        msgs.append(
                            f"{'[TEAM] ' if raw_chatmsg[0][1] == 'say_team' else ''} *[{raw_chatmsg[0][0]}]*: {raw_chatmsg[0][2]}")
                    elif raw_connectionmsg:
                        msgs.append(f"`{' '.join(raw_connectionmsg[0])}`")
                    else:
                        continue
                # print('DEBUG: list `msgs`: ', *msgs) if self.bot.debug else False
                if msgs:
                    x = "\n".join(msgs)
                    for chan in self.bot.chat_channels_obj:
                        await chan.send(x)
                for msg in msgs:
                    self.bot.bprint(f"{self.bot.game} | {''.join(msg)}")
                continue
            except Exception as e:
                print(f"Caught Unexpected {type(e)}: ({str(e)}) (Source Server Game2Guild)")
            finally:
                await asyncio.sleep(.75)

    async def chat_from_guild_to_game(self):
        with valvercon.RCON((self.bot.cfg["local_ip"], self.rcon_port), self.password) as rcon:
            while self.proc.is_running() and self.bot.is_alive:
                try:
                    msg = await self.bot.wait_for(GuildMessageCreateEvent, predicate=self.is_chat_channel, timeout=5)
                    if not hasattr(msg, 'author') or (hasattr(msg, 'author') and msg.author.is_bot):
                        pass
                    elif msg.clean_content:
                        i = len(msg.author.username)
                        # if message is longer than 200-some characters
                        if len(msg.clean_content) > 230 - i:
                            wrapped = tw.wrap(msg.clean_content, width=230 - i,
                                              initial_indent=f"{msg.author.username}: ")
                            for wrapped_line in wrapped:
                                rcon(f"say |D> {wrapped_line}")
                        # elif shorter than 200-some characters
                        else:
                            rcon(f"say |D> {msg.author.username}: {msg.clean_content}")
                        self.bot.bprint(f"Discord | <{msg.author.username}>: {msg.clean_content}")
                    if msg.attachments:
                        rcon.command(f"say |D> {msg.author.username}: Image {msg.attachments[0]['filename']}")
                        self.bot.bprint(
                            f"Discord | {msg.author.username}: Image {msg.attachments[0]['filename']}")
                except asyncio.exceptions.TimeoutError:
                    pass
                except Exception as e:
                    print(f"Caught Unexpected {type(e)}: ({str(e)}) (Source Server Guild2Game)")

    async def update_server_information(self):
        while self.proc.is_running() and self.bot.is_alive:
            try:
                info = await a2s.ainfo((self.bot.cfg["local_ip"], self.query_port))

                mode = info.game
                cur_map = info.map
                cur_p = info.player_count
                max_p = info.max_players
                cur_status = f"Playing: {self.readable_name} - {mode} on map {cur_map} ({cur_p}/{max_p} players)"

                for chan in self.bot.chat_channels_obj:
                    await chan.edit(topic=cur_status)
                await self.bot.update_presence(status=f"{self.readable_name} | "
                                                      f"{mode} on {cur_map} ({cur_p}/{max_p}) | "
                                                      f"CPU: {self.proc.cpu_percent()}% | "
                                                      f"Mem: {round(self.proc.memory_percent(), 2)}%")
            except ForbiddenError:
                print("Bot lacks permission to edit channels. (hikari.ForbiddenError)")
            except a2s.BufferExhaustedError:
                print("Buffer Exhausted (a2s.BufferExhaustedError)")
            except a2s.BrokenMessageError:
                print("Broken Message (a2s.BrokenMessageError)")
            except Exception as e:
                print(f"Error: {e} ({type(e)})")
            await asyncio.sleep(30)


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
