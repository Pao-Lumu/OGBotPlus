import hikari
import lightbulb
from OGBotPlus import OGBotPlus
from pprint import pprint
import logging


class Activity(lightbulb.Plugin):
    def __init__(self, bot):
        self.bot: OGBotPlus = bot
        super(Activity, self).__init__()

    @lightbulb.listener(hikari.events.MemberUpdateEvent)
    async def on_member_update(self, event: hikari.MemberUpdateEvent):
        if event.guild_id not in self.bot.cfg['main_guilds'] or event.member.is_bot:
            return
        old = event.old_member
        new = event.member
        if new.username != old.username:
            logging.warning(f"{old.username} changed their username to {new.username}")
        elif new.nickname != old.nickname:
            if not new.nickname:
                logging.warning(f"{new.username} deleted their nickname")
            elif not old.nickname:
                logging.warning(f"{new.username} set nickname to {new.nickname}")
            else:
                logging.warning(f"{new.username} changed nickname from {old.nickname} to {new.nickname}")

    @lightbulb.listener(hikari.PresenceUpdateEvent)
    async def on_prescence_update(self, event: hikari.PresenceUpdateEvent):
        if event.get_user().is_bot:
            return
        if event.presence and event.presence.guild_id not in self.bot.cfg['main_guilds']:
            return
        old = event.old_presence
        new = event.presence
        usr = await event.fetch_user()
        # status
        if not old:
            logging.warning(f"{usr.username} came online ({new.visible_status.name})")
        elif new.visible_status == hikari.Status.OFFLINE:
            logging.warning(f"{usr.username} went offline ({new.visible_status.name})")
        elif new.visible_status != old.visible_status:
            logging.warning(f"{usr.username} changed visibility to ({new.visible_status.name})")
        # game and spotify status
        elif old.activities != new.activities:

            before = frozenset(MiniActivity(x) for x in old.activities)
            after = frozenset(MiniActivity(x) for x in new.activities)

            if before == after:
                pass
            else:
                diff = after.symmetric_difference(before)
                for act in diff:
                    if act.type == hikari.ActivityType.LISTENING:
                        if act in after:
                            logging.warning(f"{usr.username} started listening to {act.details} by {act.state}")
                        # elif len(diff) == 1:  # commented out bcz of log spam
                        #     logging.warning(f"{usr.username} stopped listening to Spotify")
                    elif act.type == hikari.ActivityType.CUSTOM:
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
                            old_act = [x for x in diff if x != act and act.type == hikari.ActivityType.CUSTOM][0]
                            logging.warning(
                                f"{usr.username} changed custom status from "
                                f"{old_act.emoji.name if old_act.emoji else ''}{old_act.state if old_act.state else ''}"
                                f" to "
                                f"{new_act.emoji.name if new_act.emoji else ''}{new_act.state if new_act.state else ''}"
                            )
                            break
                    elif act.type == hikari.ActivityType.PLAYING:
                        if act in after:
                            logging.warning(f"{usr.username} started playing {act.name}")
                        if act in before:
                            logging.warning(f"{usr.username} stopped playing {act.name}")

    @lightbulb.listener(hikari.VoiceStateUpdateEvent)
    async def on_voice_state_update(self, event: hikari.VoiceStateUpdateEvent):
        usr = event.state.member
        old = event.old_state
        new = event.state
        if not old:
            chan = self.bot.cache.get_guild_channel(new.channel_id)
            logging.warning(f"{usr.username} joined {chan.name}")
            return
        elif not new.channel_id:
            chan = self.bot.cache.get_guild_channel(old.channel_id)
            logging.warning(f"{usr.username} left {chan.name}")
        elif old.channel_id != new.channel_id:
            old_chan = self.bot.cache.get_guild_channel(old.channel_id)
            new_chan = self.bot.cache.get_guild_channel(new.channel_id)
            logging.warning(f"{usr.username} moved from {old_chan.name} to {new_chan.name}")
        if old.is_guild_muted != new.is_guild_muted:
            if old.is_guild_muted:
                logging.warning(f"{usr.username} was unmuted by a moderator")
            else:
                logging.warning(f"{usr.username} was muted by a moderator")
        if old.is_guild_deafened != new.is_guild_deafened:
            if old.is_guild_deafened:
                logging.warning(f"{usr.username} was undeafened by a moderator")
            else:
                logging.warning(f"{usr.username} was deafened by a moderator")
        if old.is_self_muted != new.is_self_muted:
            if old.is_self_muted:
                logging.warning(f"{usr.username} unmuted themselves")
            else:
                logging.warning(f"{usr.username} muted themselves")
        if old.is_self_deafened != new.is_self_deafened:
            if old.is_self_deafened:
                logging.warning(f"{usr.username} undeafened themselves")
            else:
                logging.warning(f"{usr.username} deafened themselves")
        if old.is_streaming != new.is_streaming:
            if old.is_streaming:
                logging.warning(f"{usr.username} stopped streaming")
            else:
                logging.warning(f"{usr.username} started streaming")
        if old.is_video_enabled != new.is_video_enabled:
            if old.is_video_enabled:
                logging.warning(f"{usr.username} shut off their webcam")
            else:
                logging.warning(f"{usr.username} turned on their webcam")
        if old.is_suppressed != new.is_suppressed:
            if old.is_suppressed:
                logging.warning(f"{usr.username} was unsuppressed")
            else:
                logging.warning(f"{usr.username} was suppressed")


class MiniActivity:
    def __init__(self, obj: hikari.RichActivity):
        self.type = obj.type
        self.name = obj.name
        self.details = obj.details
        self.emoji = obj.emoji
        self.assets = obj.assets
        self.state = obj.state
        if self.type == hikari.ActivityType.PLAYING:
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