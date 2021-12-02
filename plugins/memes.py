import asyncio
import re

import hikari
import lightbulb

plugin = lightbulb.Plugin("Memes")


@plugin.listener(hikari.GuildMessageCreateEvent)
async def on_message(message: hikari.GuildMessageCreateEvent):
    if not message.content:
        return
    if message.is_bot:
        return
    else:
        plugin.app.bprint(message.content)
    msg = message.content.lower()
    if 'egg' in msg or '🥚' in msg:
        if re.match(r'what,? you egg', msg):
            await message.get_channel().send(':question:, :point_up: :egg::question:')
            return
        egg = [':egg:' for x in range(message.content.lower().count('egg') + message.content.lower().count('🥚'))]
        await message.get_channel().send(" ".join(egg))
    # if message.attachments:
    #     for attachment in message.attachments:
    #         if 'egg' in attachment.filename.lower():
    #             egg = [':egg:' for x in range(attachment.filename.lower().count('egg'))]
    #             await message.get_channel().send(" ".join(egg))
    # if 'gay' in msg:
    #     await message.channel.send("""I'm not gay. Sorry gays.""")
    await auto_thonk(message)


async def auto_thonk(msg):
    hmm = re.compile("^[Hh]+[Mm][Mm]+\\.*")
    if re.search(hmm, msg.content):
        await asyncio.sleep(.5)
        await msg.add_reaction('🤔')
