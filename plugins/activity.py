import asyncio
import logging
from typing import Dict, Any, Union

import hikari
import lightbulb
from hikari import ActivityType, MemberUpdateEvent, PresenceUpdateEvent, Status, VoiceStateUpdateEvent, RichActivity

from OGBotPlus import OGBotPlus

# import pprint

plugin = lightbulb.Plugin("Activity")

bot: Union[OGBotPlus, lightbulb.BotApp]
# print(type(bot))
lock: asyncio.Lock()
state: Dict[str, Dict[str, Any]] = {}
attrs = ['is_guild_muted', 'is_guild_deafened', 'is_self_muted', 'is_self_deafened', 'is_streaming',
         'is_video_enabled', 'is_suppressed']
lookup = {'is_guild_muted': ['{} was muted by a moderator', '} was unmuted by a moderator'],
          'is_guild_deafened': ['{} was deafened by a moderator', '{} was undeafened by a moderator'],
          'is_self_muted': ['{} muted themselves', '{} unmuted themselves'],
          'is_self_deafened': ['{} deafened themselves', '{} undeafened themselves'],
          'is_streaming': ['{} started streaming in {}', '{} stopped streaming in {}'],
          'is_video_enabled': ['{} turned on their webcam', '{} shut off their webcam'],
          'is_suppressed': ['{} was suppressed', '{} was unsuppressed']}


async def is_fresh(user_id: int, key: str, value):
    str_uid = str(user_id)
    if str_uid not in state.keys():
        state[str_uid] = {key: value,
                          key + '_future': asyncio.ensure_future(clear_from_cache(user_id, key))}
        return True
    else:
        try:
            x = state[str_uid][key]
        except KeyError:
            pass
            state[str_uid][key] = value
            if state[str_uid].get(key + '_future'):
                state[str_uid][key + '_future'].cancel()
            state[str_uid][key + '_future'] = asyncio.ensure_future(clear_from_cache(user_id, key))
            return True
        if x == value:
            return False
        else:
            state[str_uid][key] = value
            if state[str_uid][key + '_future']:
                state[str_uid][key + '_future'].cancel()
            state[str_uid][key + '_future'] = asyncio.ensure_future(clear_from_cache(user_id, key))
            return True


async def clear_from_cache(user_id: int, key: str):
    await asyncio.sleep(15)
    async with lock:
        str_uid = str(int(user_id))  # necessary to convert from snowflake to usable str for keys
        if str_uid not in state.keys():
            # pprint.pprint(state)
            return
        else:
            state[str_uid].pop(key)
            state[str_uid].pop(key + '_future')
            # pprint.pprint(state)
            return


@plugin.listener(MemberUpdateEvent)
async def on_member_update(event: MemberUpdateEvent):
    if event.guild_id not in plugin.app.cfg['main_guilds'] or event.member.is_bot:
        return
    old = event.old_member
    new = event.member
    async with lock:
        if new.username != old.username:
            if await is_fresh(new.id, "username", new.username):
                logging.warning(f"{old.username} changed their username to {new.username}")
        elif new.nickname != old.nickname:
            if await is_fresh(new.id, 'nickname', new.nickname):
                if not new.nickname:
                    logging.warning(f"{new.username} deleted their nickname")
                elif not old.nickname:
                    logging.warning(f"{new.username} set nickname to {new.nickname}")
                else:
                    logging.warning(f"{new.username} changed nickname from {old.nickname} to {new.nickname}")


@plugin.listener(PresenceUpdateEvent)
async def on_presence_update(event: PresenceUpdateEvent):
    if not event.get_user() or event.get_user().is_bot:
        return
    if event.presence and event.presence.guild_id not in plugin.app.cfg['main_guilds']:
        return
    # status
    async with lock:
        old = event.old_presence
        new = event.presence
        usr = await event.fetch_user()
        # print("print1")
        # pprint.pprint(state)
        if await is_fresh(new.user_id, 'visible_status', new.visible_status.name):
            if not old:
                logging.warning(f"{usr.username} came online ({new.visible_status.name})")
            elif new.visible_status == Status.OFFLINE:
                logging.warning(f"{usr.username} went offline ({new.visible_status.name})")
                # pprint.pprint(state)
            elif new.visible_status != old.visible_status:
                logging.warning(f"{usr.username} changed visibility to ({new.visible_status.name})")
        # game and spotify status
        if not old:
            acts = [MiniActivity(x) for x in new.activities]
            if await is_fresh(new.user_id, 'activities', acts):
                for act in acts:
                    if act.type == ActivityType.LISTENING:
                        logging.warning(f"{usr.username} started listening to {act.details} by {act.state}")
                    elif act.type == ActivityType.CUSTOM:
                        logging.warning(
                            f"{usr.username} set custom status to "
                            f"{':' + act.emoji.name + ': ' if act.emoji else ''}{act.state if act.state else ''}")
                    elif act.type == ActivityType.PLAYING:
                        logging.warning(f"{usr.username} started playing {act.name}")
        elif old.activities != new.activities:

            before = frozenset(MiniActivity(x) for x in old.activities)
            after = frozenset(MiniActivity(x) for x in new.activities)

            if before == after:
                pass
            else:
                diff = after.symmetric_difference(before)
                if await is_fresh(new.user_id, 'activities', diff):
                    for act in diff:
                        if act.type == ActivityType.LISTENING:
                            if act in after:
                                logging.warning(f"{usr.username} started listening to {act.details} by {act.state}")
                            # elif len(diff) == 1:  # commented out bcz of log spam
                            #     logging.warning(f"{usr.username} stopped listening to Spotify")
                        elif act.type == ActivityType.CUSTOM:
                            if len(diff) == 1 and act in after:
                                logging.warning(
                                    f"{usr.username} set custom status to "
                                    f"{act.emoji.name if act.emoji else ''}{act.state if act.state else ''}")
                                break
                            elif len(diff) == 1 and act in before:
                                logging.warning(f"{usr.username} cleared custom status")
                                break
                            elif len(diff) == 2 and act in after:
                                new_act = act
                                old_act = [x for x in diff if x != act and act.type == ActivityType.CUSTOM][0]
                                logging.warning(
                                    f"{usr.username} changed custom status from "
                                    f"{':' + old_act.emoji.name + ': ' if old_act.emoji else ''}"
                                    f"{old_act.state if old_act.state else ''} to "
                                    f"{':' + new_act.emoji.name + ': ' if new_act.emoji else ''}"
                                    f"{new_act.state if new_act.state else ''}"
                                )
                                break
                        elif act.type == ActivityType.PLAYING:
                            # hopefully this reduces log spam
                            if len(diff) == 2:
                                diff_list = [x for x in diff]
                                if diff_list[0].name == diff_list[1].name:
                                    return
                                elif act in after:
                                    logging.warning(f"{usr.username} started playing {act.name}")
                            elif len(diff) == 1:
                                if act in after:
                                    logging.warning(f"{usr.username} started playing {act.name}")
                                if act in before:
                                    logging.warning(f"{usr.username} stopped playing {act.name}")


@plugin.listener(VoiceStateUpdateEvent)
async def on_voice_state_update(event: VoiceStateUpdateEvent):
    usr = event.state.member
    old = event.old_state
    new = event.state
    if not old:
        chan = plugin.app.cache.get_guild_channel(new.channel_id)
        logging.warning(f"{usr.username} joined {chan.name}")
        return
    elif not new.channel_id:
        chan = plugin.app.cache.get_guild_channel(old.channel_id)
        logging.warning(f"{usr.username} left {chan.name}")
    elif old.channel_id != new.channel_id:
        old_chan = plugin.app.cache.get_guild_channel(old.channel_id)
        new_chan = plugin.app.cache.get_guild_channel(new.channel_id)
        logging.warning(f"{usr.username} moved from {old_chan.name} to {new_chan.name}")

    for attr in attrs:
        old_attr = old.__getattribute__(attr)
        new_attr = new.__getattribute__(attr)
        if old_attr != new_attr:
            if new_attr:
                if attr == 'is_streaming':
                    chan = plugin.app.cache.get_guild_channel(new.channel_id)
                    logging.warning(lookup[attr][0].format(usr.username, chan.name))
                else:
                    logging.warning(lookup[attr][0].format(usr.username))
            else:
                if attr == 'is_streaming':
                    chan = plugin.app.cache.get_guild_channel(old.channel_id)
                    logging.warning(lookup[attr][1].format(usr.username, chan.name))
                else:
                    logging.warning(lookup[attr][1].format(usr.username))


class MiniActivity:
    def __init__(self, obj: RichActivity):
        self.type = obj.type
        self.name = obj.name
        self.details = obj.details
        self.emoji = obj.emoji
        self.assets = obj.assets
        self.state = obj.state
        if self.type == ActivityType.PLAYING:
            pass

    def __eq__(self, other):
        try:
            if hash(self) == hash(other):
                return True
            else:
                return False
        except TypeError:
            print("FAIL")
            return False

    def __hash__(self):
        return hash((self.type, self.name, self.details, self.emoji, self.state))
