import asyncio
import json
import logging
import os
import pickle
import random
import sqlite3

import hikari
import lightbulb

from utils import embeds
from utils.emoji import Emoji as emoji

plugin = lightbulb.Plugin("Santa")

santa_sql_lock = asyncio.Lock()
try:
    with open("data/ogbox.json") as sec:
        lookup: dict = json.load(sec)
        uplook: dict = {v: k for k, v in lookup.items()}
except FileNotFoundError:
    with open("data/ogbox.json", 'w') as file:
        json.dump({"PERSON": 0}, file)
    pass

if not os.path.exists('data/santa.sql'):
    conn = sqlite3.connect('data/santa.sql')
    cursor = conn.cursor()
    cursor.execute(
        "CREATE TABLE santa(user_id, user_name, gifter_id, gifter_name, giftee_id, giftee_name)")
    cursor.execute("CREATE TABLE questions(message_id, question, message_responses)")
    conn.commit()
else:
    conn = sqlite3.connect('data/santa.sql')
    cursor = conn.cursor()


@plugin.listener(hikari.events.GuildReactionAddEvent)
async def on_raw_reaction_add(reaction: hikari.events.GuildReactionAddEvent):
    try:
        author = reaction.member
    except:
        return
    if reaction.channel_id == plugin.app.santa_channel and reaction.emoji_name == emoji.BALLOT_BOX:
        channel = plugin.app.cache.get_guild_channel(reaction.channel_id)
        msg_ref = await channel.fetch_message(reaction.message_id)

        async with santa_sql_lock:
            try:
                cursor.execute("SELECT question, message_responses FROM questions WHERE message_id=?",
                                    (reaction.message_id,))
                q, pickled_responses = cursor.fetchone()
            except TypeError:
                return
        responses: dict = pickle.loads(pickled_responses)
        while True:
            sent = await author.send(f'The question you have been asked is: {q}\nType your response below.')
            asyncio.ensure_future(delete(sent, 120))

            message = await plugin.app.wait_for(hikari.DMMessageCreateEvent, timeout=120.0, predicate=lambda
                msg: author == msg.author and msg.channel_id == sent.channel_id)
            responses[str(reaction.user_id)] = message.content

            e = hikari.Embed(title="Somebody asked...", description='{}\n\n`VVVV Responses VVVV`'.format(q))
            for x, y in responses.items():
                e.add_field(name=uplook[int(x)], value=y, inline=False)

            preview = await send_with_yes_no_reactions(author,
                                                            message=f'''Does this look correct?\n({emoji.THUMBS_UP} for yes, {emoji.THUMBS_DOWN} for no)''',
                                                            embed=e)
            try:
                confirmation = await get_confirmation(author, preview)
                if confirmation:
                    await preview.delete()
                    sent = await author.send(
                        'Okay, your response will be sent.\nYou may edit it by reacting to the question again.')
                    await msg_ref.edit(embed=e)

                    async with santa_sql_lock:
                        try:
                            cursor.execute("SELECT message_responses FROM questions WHERE message_id=?",
                                                (reaction.message_id,))

                            responses = pickle.loads(cursor.fetchone()[0])
                            responses[str(author.id)] = message.content
                            pickled_responses = pickle.dumps(responses)

                            cursor.execute("UPDATE questions SET message_responses=? WHERE message_id=?",
                                                (pickled_responses, reaction.message_id,))
                            conn.commit()

                            e = hikari.Embed(title="Somebody asked...", description=q)
                            for x, y in responses.items():
                                e.add_field(name=uplook[int(x)], value=y, inline=False)

                        except Exception as e:
                            await send_error_user(author, e)
                        finally:
                            conn.commit()
                            break
                else:
                    continue
            except asyncio.TimeoutError:
                dm_channel = await author.fetch_dm_channel()
                await dm_channel.send('Timed out. Please try again.')
                break
            except Exception as e:
                await send_error_user(author, e)


@plugin.command
@lightbulb.add_checks(*[lightbulb.checks.dm_only, lightbulb.checks.human_only])
@lightbulb.command("secret", """Check who your giftee for this year's secret santa is.
Owner Only: Generate/regenerate all secret santa assignments.""")
@lightbulb.implements(lightbulb.commands.PrefixCommand)
async def secret( ctx: lightbulb.context.base.Context):
    """Check who your giftee for this year's secret santa is.
Owner Only: Generate/regenerate all secret santa assignments.
    """
    if ctx.author.id in plugin.app.owner_ids:
        async with santa_sql_lock:
            people = list()
            for x, y in lookup.items():
                people.append(x)

            continue_go = True
            while continue_go:
                random.shuffle(people)

                used_combos = [
                    # Combos from 2018
                    # ('Evan', 'Aero'), ('Aero', 'Zach'), ('Zach', 'Brandon'), ('Brandon', 'Jeromie'),
                    # ('Jeromie', 'Steven'), ('Steven', 'David'), ('David', 'Evan'),

                    # Combos from 2019
                    ('Evan', 'Brandon'), ('Brandon', 'Aero'), ('Aero', 'Jeromie'), ('Jeromie', 'Zach'),
                    ('Zach', 'CJ'), ('CJ', 'David'), ('David', 'Steven'), ('Steven', 'Evan'),

                    # Combos from 2020
                    ('Evan', 'Cameron'), ('Cameron', 'CJ'), ('CJ', 'Allen'), ('Allen', 'David'), ('David', 'Zach'),
                    ('Zach', 'Jeromie'), ('Jeromie', 'Evan'),
                    ('Steven', 'Aero'), ('Aero', 'Brandon'), ('Brandon', 'Steven')
                ]
                banned_combos = [('Evan', 'Zach'), ('CJ', 'Forester'), ('Jon', 'Evan'), ('Jon', 'Forester'),
                                 ('Allen', 'Forester'), ('Cameron', 'Forester'), ('Jon', 'Cameron'),
                                 ('Lexi', 'Allen'), ('Lexi', 'CJ'), ('Lexi', 'Cameron'), ('Lexi', 'Forester'),
                                 ('Lexi', 'David'), ('Lexi', 'Steven')]

                continue_go = check_for_combos(people, used_combos, banned_combos)

            cursor.execute('DELETE FROM santa')

            for x, person in enumerate(people):
                b, g, a = (x - 1) % len(people), x % len(people), (x + 1) % len(people)
                the_world = (
                    lookup[people[b]], people[b], lookup[people[g]], people[g], lookup[people[a]],
                    people[a])
                cursor.execute('INSERT INTO santa VALUES (?,?,?,?,?,?)', the_world)
            conn.commit()

        for x, person in enumerate(people):
            try:
                discord_id = lookup[person]
                gifter = person
                giftee = people[(x + 1) % len(people)]
                e = hikari.Embed()
                e.title = "{}, you are {}'s secret santa.".format(gifter, giftee)
                e.description = """
Use `>ask` if you'd like to ask them their shirt size, shoe size, favorite color, etc. directly
Use `>respond` if your secret santa `>ask`s you a question via DM and you want to respond.

Use `>askall` to ask all participants a question.
To respond to an `>askall` question, click/tap the checkmark under it. You should get a DM from this bot explaining how to respond.

*It's recommended that you go invisible on Discord when you send `>ask` questions, since I can't prevent people from puzzling things out from who's online.*

Recommended price: Try for under $30, but going slightly over if the need arises is acceptable. Just don't blow hundreds on a gift.
Secret Santa gifts can be silly or serious.

Please try not to give away who you are to your secret santa, as that ruins the fun of the event.
Misleading your secret santa is allowed & encouraged.
"""
                member = plugin.app.cache.get_user(discord_id)
                await member.send(embed=e)
            except Exception as e:
                await send_error_ctx(ctx, e)
    else:
        async with santa_sql_lock:
            try:
                cursor.execute('SELECT * FROM santa WHERE user_id=?', (ctx.author.id,))
                u_id, u_name, _, _, g_id, g_name = cursor.fetchone()
                await ctx.respond("{}, you have been assigned {}'s secret santa.".format(u_name, g_name))
            except TypeError:
                await ctx.respond("You're not a secret santa! If you think this is in error, talk to Evan.")
            except Exception as e:
                await send_error_ctx(ctx, e)
                pass


@plugin.command
@lightbulb.add_checks(lightbulb.dm_only, lightbulb.human_only)
@lightbulb.command("ask","""Ask your assigned giftee a question.""")
@lightbulb.implements(lightbulb.commands.PrefixCommand)
async def ask( ctx: lightbulb.context.base.Context):
    """Ask your assigned giftee a question."""
    async with santa_sql_lock:
        try:
            cursor.execute('SELECT * FROM santa WHERE user_id=?', (ctx.author.id,))
            u_id, u_name, _, _, g_id, g_name = cursor.fetchone()
        except KeyError:
            await ctx.respond("You're not in the secret santa group!")
        except TypeError:
            await ctx.respond("Your secret santa has not been assigned!")
    nn = ctx.event.message.content.lstrip(str(ctx.prefix) + str(ctx.command)).lstrip()
    if nn:
        member = plugin.app.cache.get_user(int(g_id))
        msg = "`>ask` message from your gifter:\n`{}`".format(nn)
        try:
            await member.send(content=msg)
            await ctx.respond("Message Sent!")
        except:
            await ctx.respond("Message may have failed to send. Consult Evan.")
    else:
        await ctx.respond("Please add a message.")


@plugin.command
@lightbulb.add_checks(lightbulb.dm_only, lightbulb.human_only)
@lightbulb.command("respond", """Respond to your gifter.""")
@lightbulb.implements(lightbulb.commands.PrefixCommand)
async def respond( ctx: lightbulb.context.base.Context):
    """Respond to your gifter."""
    async with santa_sql_lock:
        try:
            cursor.execute('SELECT * FROM santa WHERE user_id=?', (ctx.author.id,))
            u_id, u_name, g_id, g_name, _, _ = cursor.fetchone()
        except KeyError:
            await ctx.respond("You're not in the secret santa group!")
            return
        except TypeError:
            await ctx.respond("Your secret santa has not been assigned!")
            return
    nn = ctx.event.message.content.lstrip(ctx.prefix).lstrip(ctx.command.name).lstrip()
    if nn:
        member: hikari.User = plugin.app.cache.get_user(int(g_id))
        msg = "`>respond` message from your giftee, {}:\n`{}`".format(u_name, nn)
        try:
            await member.send(content=msg)
            await ctx.respond("Message Sent!")
        except hikari.ForbiddenError:
            await ctx.respond("Message may have failed to send. Consult Evan.")
    else:
        await ctx.respond("Please add a message.")


@plugin.command
@lightbulb.add_checks(lightbulb.dm_only, lightbulb.human_only)
@lightbulb.command("askall", """Send a question to the main server's questions channel for everyone to respond to.""")
@lightbulb.implements(lightbulb.commands.PrefixCommand)
async def askall( ctx: lightbulb.context.base.Context):
    """Send a question to the main server's questions channel for everyone to respond to."""
    if ctx.get_channel():
        await ctx.respond('Please use DMs to set up polls.')
        return
    rcvr = ctx.author
    message = ctx.event.message
    while True:
        try:
            if not message:
                await ctx.respond(
                    'Please type your question. (If no response is received within 2 minutes, this will time out and you will have to type `>askall` or `>poll` again.)')
                message = await plugin.app.wait_for(hikari.DMMessageCreateEvent, timeout=120.0,
                                                    predicate=lambda msg: rcvr == msg.author)
            e = hikari.Embed(color=hikari.Color.from_rgb(0, 255, 0))
            question = message.content.lstrip(ctx.prefix).lstrip(ctx.command.name)
            for x in ctx.command.aliases:
                question = question.lstrip(str(x))
            if question == '':
                message = ''
                continue
            e.title = '_*Someone asked:*_'
            e.description = '{}\n\n`Responses: `'.format(question)
            preview = await send_with_yes_no_reactions(rcvr,
                                                            message='This is how your question will look. Are you sure you want to send this message?',
                                                            embed=e, extra_reactions=(emoji.CROSS_MARK,))
            try:
                confirmation = await get_confirmation(rcvr, message=preview)
                if confirmation:
                    s = await ctx.respond('Sending...')
                    mm = await plugin.app.cache.get_guild_channel(plugin.app.santa_channel).send(embed=e)
                    await mm.add_reaction(emoji.BALLOT_BOX)

                    async with santa_sql_lock:
                        cursor.execute("INSERT INTO questions VALUES (?,?,?)",
                                            (mm.id, question, pickle.dumps(dict())))
                        conn.commit()
                    await s.edit('Message sent!')
                    break
                else:
                    await ctx.respond('Okay, restarting...')
                    message = ''
                    continue
            except asyncio.CancelledError:
                await preview.delete()
                msg = await ctx.respond('Okay, canceled question creation.')
                asyncio.ensure_future(delete(msg, 30))
                break
        except asyncio.TimeoutError:
            msg = await ctx.respond('Timed out. Please send the command again.')
            asyncio.ensure_future(delete(msg, 30))
            break
        except Exception as e:
            await send_error_ctx(ctx, e)


async def send_with_yes_no_reactions( receiver: hikari.User, message: str = None,
                                     embed: hikari.Embed = None, extra_reactions: tuple = ()):
    reactions = [emoji.THUMBS_UP, emoji.THUMBS_DOWN]

    reactions.extend(extra_reactions)

    dm_channel = await receiver.fetch_dm_channel()
    msg = await dm_channel.send(message, embed=embed)
    asyncio.ensure_future(delete(msg, 120))

    try:
        for x in reactions:
            await msg.add_reaction(x)

    except Exception as e:
        await send_error_user(receiver, e)

    return msg


async def get_confirmation( rcvr, message: hikari.Message = None, timeout=120.0):
    rcvr_dm = await rcvr.fetch_dm_channel()

    def same_channel(rctn: hikari.DMReactionAddEvent):
        if message:
            return rcvr.id == rctn.user_id and \
                   rctn.channel_id == rcvr_dm.id and \
                   rctn.message_id == message.id
        else:
            return rcvr.id == rctn.user_id and rctn.message.channel == rcvr.dm_channel

    reaction = await plugin.app.wait_for(hikari.DMReactionAddEvent, timeout=timeout, predicate=same_channel)
    if reaction.emoji_name == emoji.THUMBS_UP:
        return True
    elif reaction.emoji_name == emoji.THUMBS_DOWN:
        return False
    else:
        raise asyncio.CancelledError


def check_for_combos(check_list, ban_list, superban_list):
    for x, g in enumerate(check_list):
        r = check_list[(x + 1) % len(check_list)]
        if (g, r) in ban_list:
            break
        if (g, r) in superban_list or (r, g) in superban_list:
            break
    else:
        return False
    return True


async def delete(msg, delay):
    await asyncio.sleep(delay)
    try:
        await msg.delete()
    except hikari.errors.NotFoundError:
        pass


async def send_error_user( rcvr: hikari.User, e):
    # await rcvr.send(f'Something has gone wrong. Evan has been notified.\nError: {type(e)}: {e}')
    # plugin.app.bprint(f'{type(e)}: {e}')
    await rcvr.send(
        embed=embeds.error_embed(f'Something has gone wrong. Evan has been notified.\nError: {type(e)}: {e}'))
    logging.warning(f'{type(e)}: {e}')
    await plugin.app.cache.get_user(list(plugin.app.owner_ids)[0]).send(embeds.error_embed(f'{type(e)}: {e}'))


async def send_error_ctx( rcvr: lightbulb.context.base.Context, e):
    # await rcvr.respond(f'Something has gone wrong. Evan has been notified.\nError: {type(e)}: {e}')
    # plugin.app.bprint(f'{type(e)}: {e}')
    await rcvr.respond(
        embed=embeds.error_embed(f'Something has gone wrong. Evan has been notified.\nError: {type(e)}: {e}'))
    logging.warning(f'{type(e)}: {e}')
    await plugin.app.cache.get_user(list(plugin.app.owner_ids)[0]).send(embeds.error_embed(f'{type(e)}: {e}'))

# Real Numbers
# group = {
#     "Evan": 141752316188426241,
#     "Brandon": 146777902501855232,
#     "Steven": 155794959365046273,
#     "David": 158704434954764288,
#     "Zach": 159388909346750465,
#     "Aero": 239192698836221952,
#     "Jeromie": 249639501004144640,
#     "CJ": 530099291478556701
# }

# Fake Numbers for testing
# group = {
#     "Evan": 141752316188426241,
#     "Brandon": 141752316188426241,
#     "Steven": 141752316188426241,
#     "David": 141752316188426241,
#     "Zach": 141752316188426241,
#     "Aero": 141752316188426241,
#     "Jeromie": 141752316188426241,
#     "CJ": 141752316188426241
# }
