import logging
from os import listdir
from os.path import join, isfile, exists
import random
import asyncio

import hikari
import lightbulb

from OGBotPlus import OGBotPlus


class Admin(lightbulb.Plugin):
    def __init__(self, bot):
        self.bot: OGBotPlus = bot
        super().__init__()

    @lightbulb.listener(hikari.GuildAvailableEvent)
    async def change_server_icon(self, event: hikari.GuildAvailableEvent):
        if int(self.bot.get_me().id) == 370679673904168975 or int(event.guild_id) != 892947625366671410:
            return
        icon_dir_path = join('data', 'server_icons')
        last_icon = ''

        while self.bot.is_alive:
            if exists(icon_dir_path):
                icons = [f for f in listdir(icon_dir_path) if isfile(join(icon_dir_path, f))]
                if not icons:
                    await asyncio.sleep(1800)  # sleep for half an hour
                    continue
                try:
                    ind = icons.index(last_icon)
                    if ind:
                        icons.pop(ind)
                except ValueError:
                    pass
                random.shuffle(icons)
                guild = self.bot.cache.get_guild(892947625366671410)
                await guild.edit(icon=join(icon_dir_path, icons[0]))
                logging.warning(f'Set server icon to {icons[0]}')
                last_icon = icons[0]
            await asyncio.sleep(1800)  # sleep for half an hour