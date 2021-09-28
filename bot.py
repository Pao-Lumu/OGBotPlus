#!/usr/bin/env python3

import hikari
import lightbulb
import asyncio
# import aiofiles
import toml
import pyfiglet
import datetime
import pprint
from plugins.warframe import Warframe
import logging.handlers
import sys
import os

if os.name != "nt":
    import uvloop
    uvloop.install()

# Logging setup

fmt = logging.Formatter('%(asctime)s - %(message)s', datefmt="%Y-%m-%d %H:%M:%S")

log = logging.getLogger()
sh = logging.StreamHandler(sys.stderr)
sh.setFormatter(fmt)
sh.setLevel(logging.INFO)
log.addHandler(sh)

discord_logger = logging.getLogger('hikari')
discord_logger.setLevel(logging.WARNING)
discord_logger.addHandler(sh)

log_path = os.path.join("logs", "ogbot.log")
if not os.path.exists(log_path):
    os.makedirs("logs", exist_ok=True)
    with open(log_path, "x") as f:
        pass

fh = logging.handlers.TimedRotatingFileHandler(filename=log_path, when="midnight", encoding='utf-8')
fh.setFormatter(fmt)
discord_logger.addHandler(fh)
log.addHandler(fh)

log = logging.getLogger()


def load_config() -> dict:
    default = {"credentials": {'token': '', 'client_id': ''},
               "bot_configuration": {'tracked_guild_ids': [], 'chat_channel': 0, 'default_rcon_password': '',
                                     'santa_channel': 0, 'local_ip': '127.0.0.1'}}

    try:
        with open('config.toml') as cfg:
            dd_config = toml.load(cfg)
            for k1, v1 in default.items():
                if k1 not in dd_config.keys():
                    dd_config[k1] = v1
                if isinstance(v1, dict):
                    for k2, v2 in v1.items():
                        if k2 not in dd_config[k1].keys():
                            dd_config[k1][k2] = v2

        with open('config.toml', 'w') as cfg:
            toml.dump(dd_config, cfg)
        return dd_config
    except FileNotFoundError:
        log.warning('File "config.toml" not found; Generating...')
        with open('config.toml', 'w+') as cfg:
            toml.dump(default, cfg)
        print('File "config.toml" not found; Generating...')
        print('Please input any relevant information and restart.')
        return {}


config = load_config()

# bot = lightbulb.Bot(token=config['credentials']['token'], intents=hikari.Intents.ALL, slash_commands_only=True)
bot = lightbulb.Bot(token=config['credentials']['token'], intents=hikari.Intents.ALL, prefix='.')


@bot.listen(hikari.ShardReadyEvent)
async def on_ready(event: hikari.ShardReadyEvent):
    # bot.chat_channel = bot.get_channel(config['bot_configuration']['chat_channel'])
    # bot.meme_channel = bot.get_channel(config['bot_configuration']['santa_channel'])
    bot_user = bot.get_me()
    # pprint.pprint(dir(bot_user))
    print(f"""~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
{pyfiglet.figlet_format(bot_user.username, font='epic')}
Username: {bot_user.username}  |  ID: {bot_user.id}
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~""")
# Chat Channel: {config['bot_configuration']['chat_channel']}  |  Meme Channel: {config['bot_configuration']['meme_channel']}

    # await asyncio.sleep(3)
    # bot.cli = OGBotCmd(bot.loop, bot)
    # try:
        # await bot.cli.start()
    # finally:
        # await bot.close()


bot.add_plugin(Warframe(bot))
bot.run()
