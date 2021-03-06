import logging
import os
import re
import sqlite3
from typing import Union

import hikari
import lightbulb

# from OGBotPlus import OGBotPlus
from utils import embeds

plugin = lightbulb.Plugin("Chat")

if not os.path.exists('data/no_mic_channels.sql'):
    conn: sqlite3.Connection = sqlite3.connect('data/no_mic_channels.sql')
    cursor: sqlite3.Cursor = conn.cursor()
    cursor.execute(
        "CREATE TABLE channels(guild_id, voice_channel_id, text_channel_id, role_id)")
    conn.commit()
else:
    conn: sqlite3.Connection = sqlite3.connect('data/no_mic_channels.sql')
    cursor: sqlite3.Cursor = conn.cursor()


@plugin.listener(hikari.VoiceStateUpdateEvent)
async def on_update_voice_state(event: hikari.VoiceStateUpdateEvent):
    guild = plugin.app.cache.get_guild(event.guild_id)
    if event.state.channel_id is None:  # on channel leave
        # User left voice channel -> remove text channel role
        chan = plugin.app.cache.get_guild_channel(event.old_state.channel_id)
        sql_result = get_matching_entry(int(guild.id), int(chan.id))
        [await event.state.member.remove_role(guild.get_role(role_id)) for _, _, _, role_id in sql_result]
    elif event.old_state is None:  # on channel join
        # User joined voice channel -> add text channel role
        chan = plugin.app.cache.get_guild_channel(event.state.channel_id)

        sql_result = get_matching_entry(int(guild.id), int(chan.id))

        [await event.state.member.add_role(guild.get_role(role_id)) for _, _, _, role_id in sql_result]
    elif event.old_state.channel_id != event.state.channel_id:  # on channel swap
        chan1 = plugin.app.cache.get_guild_channel(event.old_state.channel_id)
        sql_result1 = get_matching_entry(int(guild.id), int(chan1.id))

        [await event.state.member.remove_role(guild.get_role(role_id)) for _, _, _, role_id in sql_result1]

        chan2 = plugin.app.cache.get_guild_channel(event.state.channel_id)
        sql_result2 = get_matching_entry(int(guild.id), int(chan2.id))

        [await event.state.member.add_role(guild.get_role(role_id)) for _, _, _, role_id in sql_result2]


@plugin.command
@lightbulb.add_checks(lightbulb.guild_only)
@lightbulb.command("pair", "Pair a chat channel to a voice channel and a role")
@lightbulb.implements(lightbulb.commands.PrefixCommand)
async def pair(
        ctx: lightbulb.context.base.Context,
        voice_ref: Union[int, str],
        role_ref: Union[int, hikari.Role, str]):
    guild = plugin.app.cache.get_guild(ctx.guild_id)
    text_channel = guild.get_channel(ctx.channel_id)

    try:
        if isinstance(voice_ref, int):
            voice = guild.get_channel(voice_ref)
        elif isinstance(voice_ref, str):
            voice = [channel for (_, channel) in guild.get_channels().items() if
                     channel.name == voice_ref and channel.type == hikari.ChannelType.GUILD_VOICE][0]
        else:
            em = embeds.error_embed("SOMETHING HAS GONE HORRIBLY WRONG (Defaulted through voice definition)")
            await ctx.respond(embed=em)
            return
    except (AttributeError, IndexError) as e:
        logging.warning(type(e))
        em = embeds.error_embed(f"Couldn't find voice channel `{voice_ref}`")
        await ctx.respond(embed=em)
        return

    try:
        if isinstance(role_ref, (int, hikari.Role)):
            role = guild.get_role(role_ref)
        elif isinstance(role_ref, str):
            role = [r for (_, r) in guild.get_roles().items() if r.name == role_ref][0]
        else:
            em = embeds.error_embed("SOMETHING HAS GONE HORRIBLY WRONG (Defaulted through role definition)")
            await ctx.respond(embed=em)
            return
    except (AttributeError, IndexError) as e:
        logging.warning(type(e))
        em = embeds.error_embed(f"Couldn't find role `{role_ref}`")
        await ctx.respond(embed=em)
        return

    sql_result = cursor.execute("SELECT voice_channel_id, text_channel_id FROM channels WHERE guild_id=?",
                                (guild.id,))

    matches = [
        (int(text_channel.id) == tc_id, vc_id, int(voice.id) == vc_id, tc_id) for vc_id, tc_id in sql_result if
        tc_id == int(text_channel.id) or vc_id == int(voice.id)]

    for matches_text, matched_voice_id, matches_voice, matched_text_id in matches:
        try:
            if matches_text:
                vc_name = guild.get_channel(matched_voice_id).name
                tc_name = guild.get_channel(matched_text_id).name
                em = embeds.info_embed(f"""`{tc_name}` is already registered to voice chat `{vc_name}`.
Type `>unpair {matched_voice_id}` to unpair them.""")
                await ctx.respond(embed=em)
                break
            elif matches_voice:
                vc_name = guild.get_channel(matched_voice_id).name
                tc_name = guild.get_channel(matched_text_id).name
                em = embeds.info_embed(f"""{vc_name} is already registered to text chat `{tc_name}`.
Type `>unpair {matched_voice_id}` to unpair them.""")
                await ctx.respond(embed=em)

                break
        except AttributeError:
            vc_name = f"deleted or inaccessible voice chat with id `{matched_voice_id}`."
            tc_name = f"deleted or inaccessible text chat with id `{matched_text_id}`."

    else:
        em = embeds.success_embed(
            f"Paired voice chat `{voice.name}` with text chat `{text_channel.name}` for Role `{role.name}`")
        await ctx.respond(embed=em)
        cursor.execute("INSERT INTO channels VALUES (?,?,?,?)",
                       (guild.id, voice.id, text_channel.id, role.id))
        conn.commit()


@plugin.command
@lightbulb.add_checks(lightbulb.guild_only)
@lightbulb.command("unpair", "Unpairs channels")
@lightbulb.implements(lightbulb.commands.PrefixCommand)
async def unpair(ctx: lightbulb.context.base.Context, channel_ref: Union[int, str, hikari.GuildChannel]):
    guild = ctx.get_guild()

    if isinstance(channel_ref, int):
        channel_id = channel_ref
    elif isinstance(channel_ref, hikari.GuildChannel):
        channel_id = int(channel_ref.id)
    elif isinstance(channel_ref, str):
        try:
            if re.search(r"\d{7,}", channel_ref) is not None:
                channel_id = re.search(r"\d{7,}", channel_ref)[0]
            else:
                channel_id = int(
                    [chan for (_, chan) in guild.get_channels().items() if chan.name == channel_ref][0].id)
        except ValueError:
            em = embeds.error_embed(f"Couldn't find a channel with exact name `{channel_ref}`")
            await ctx.respond(embed=em)
            return
    else:
        em = embeds.error_embed("SOMETHING HAS GONE HORRIBLY WRONG (Defaulted through channel id definition)")
        await ctx.respond(embed=em)
        return

    sql_result = cursor.execute(
        "SELECT * FROM channels WHERE (guild_id =:guild AND voice_channel_id =:chan_id) OR (guild_id =:guild AND text_channel_id =:chan_id)",
        {"guild": int(guild.id), "chan_id": channel_id})

    for w, x, y, z in sql_result:
        cursor.execute(
            "DELETE FROM channels WHERE (guild_id =:guild AND voice_channel_id =:chan_id) OR (guild_id =:guild AND text_channel_id =:chan_id)",
            {"guild": int(guild.id), "chan_id": channel_id})
        conn.commit()
        try:
            voice_channel = guild.get_channel(x)
        except AttributeError:
            voice_channel = x
        try:
            text_channel = guild.get_channel(y)
        except AttributeError:
            text_channel = y
        em = embeds.success_embed(f"Unpaired voice chat `{voice_channel}` with text chat `{text_channel}`.")
        await ctx.respond(embed=em)
        break
    else:
        channel = guild.get_channel(channel_id)
        em = embeds.info_embed(
            f"{'Voice' if channel.type == 2 else 'Text'} channel `{channel.name}`is not paired to any {'voice' if channel.type == 0 else 'text'} channel.")
        await ctx.respond(embed=em)


def get_matching_entry(guild_id: int, channel_id: int):
    return cursor.execute("SELECT * FROM channels WHERE (guild_id =:guild AND voice_channel_id =:chan_id)",
                          {"guild": guild_id, "chan_id": channel_id})
