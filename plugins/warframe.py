import asyncio
import json
import random
import re
import time
from datetime import datetime

import aiohttp
import hikari
import lightbulb
import pytz
from lightbulb import commands

plugin = lightbulb.Plugin(name="Warframe", description="Various commands relating to Warframe and the Warframe Market")

try:
    with open('data/wf_market_items.json') as file:
        x = json.load(file)
        wf_mkt_items = x['items']
        wf_mkt_last_update = x['last_update']
except (FileNotFoundError, json.JSONDecodeError):
    wf_mkt_items = []
    wf_mkt_last_update = 0


async def get(session: aiohttp.ClientSession, url: str):
    async with session.get(url) as response:
        if response.status != 200:
            raise NameError(f'Request threw error {response.status}')
        else:
            return await response.text()


async def get_item_info(name=None):
    async with aiohttp.ClientSession() as session:
        response = await get(session, f"https://api.warframe.market/v1/items{'/' + name if name else ''}")
        return json.loads(response) if name else json.loads(response)['payload']['items']


async def get_item_orders(name):
    async with aiohttp.ClientSession() as session:
        response = await get(session, f"https://api.warframe.market/v1/items/{name}/orders")
        return json.loads(response)


async def get_item_statistics(name):
    async with aiohttp.ClientSession() as session:
        response = await get(session, f"https://api.warframe.market/v1/items/{name}/statistics?include=item")
        return json.loads(response)


@plugin.command
@lightbulb.command("baro", "See when and where Baro Ki'teer is coming, and what he has when he is")
@lightbulb.implements(commands.SlashCommand, lightbulb.commands.PrefixCommand)
async def baro(ctx: lightbulb.context.Context) -> None:
    async with aiohttp.ClientSession() as session:
        async with session.get('https://api.warframestat.us/pc/voidTrader') as resp:
            info = await resp.json()

    hr_active = pytz.timezone('America/Chicago').fromutc(datetime.fromisoformat(info['activation'][:-1])) \
        .strftime("%A, %B %d, %Y at %I:%M %p %Z")
    hr_expiry = pytz.timezone('America/Chicago').fromutc(datetime.fromisoformat(info['expiry'][:-1])) \
        .strftime("%A, %B %d, %Y at %I:%M %p %Z")

    c = hikari.Colour.from_rgb(random.randint(0, 255), random.randint(0, 255), random.randint(0, 255))
    if not info['active']:
        embd = hikari.Embed(title=f'{info["character"]} (Void Trader)', color=c,
                            # description="{} will arrive at {} on {} ({}) and will stay until {} ({})".format(
                            #     info['character'], info['location'], hr_active, info['startString'], hr_expiry,
                            #     info['endString'])
                            )
        embd.add_field("Location", info['location']) \
            .add_field("Arrival Date", hr_active, inline=True) \
            .add_field("Time until Arrival", info['startString'], inline=True) \
            .add_field("-=-=-=-=-=-=-=-=-", "-=-=-=-=-=-=-=-=-") \
            .add_field("Departure Date", hr_expiry, inline=True) \
            .add_field("Time until Departure", info['endString'], inline=True)
        await ctx.respond(embed=embd)
    else:
        embd = hikari.Embed(title="Void Trader Offerings", color=c)
        embd.set_footer(text=info["character"])
        for offer in info['inventory']:
            embd.add_field(name=offer['item'], value=f"{offer['ducats']} ducats + {offer['credits']} credits",
                           inline=True)

        message = "{0} is currently at {1}, and will leave on {2} {3}.".format(info['character'], info['location'],
                                                                               hr_expiry, info['endString'])

        await ctx.respond(message, embed=embd)


@plugin.command
@lightbulb.add_checks(lightbulb.human_only)
@lightbulb.command("nightwave", """Lists all current Nightwave missions""", aliases=['nw'])
@lightbulb.implements(commands.SlashCommand, commands.PrefixCommand)
async def nightwave(ctx):
    async with aiohttp.ClientSession() as session:
        async with session.get('https://api.warframestat.us/pc/nightwave') as resp:
            info = await resp.json()

    if info["active"]:
        e = hikari.Embed(title="Nightwave Challenges", description="All currently active Nightwave challenges\n\n")
        e.set_footer(text="Nora Night")

        last_mission_type = ""
        for challenge in info['activeChallenges']:
            if 'isDaily' in challenge.keys() and challenge['isDaily']:
                misson_type = "Daily"
            elif challenge['isElite']:
                misson_type = "Elite Weekly"
            else:
                misson_type = "Weekly"

            if misson_type != last_mission_type:
                e.add_field("-=-=-=-=-=-=-=-=-", f"***{misson_type} Missions***")
            e.add_field(name=f"{challenge['title']} ({challenge['reputation']} standing)",
                        value=f"{challenge['desc']}", inline=True)
            last_mission_type = misson_type
        await ctx.respond(embed=e)
    else:
        await ctx.respond("Nightwave is currently inactive.")


@plugin.command
@lightbulb.add_checks(lightbulb.human_only)
@lightbulb.command("rifts", """Lists all current void fissures""", aliases=['voidrifts', 'rift', 'void'])
@lightbulb.implements(commands.SlashCommand, commands.PrefixCommand)
async def rifts(ctx):
    async with aiohttp.ClientSession() as session:
        async with session.get('https://api.warframestat.us/pc/fissures') as resp:
            info = await resp.json()
    info.sort(key=lambda x: (x['tierNum'], x['isStorm'], x['missionType']))
    last_rift = {'tierNum': -1, 'isStorm': False}
    if len(info):
        e = hikari.Embed(title="Void Fissures", description="All currently active void fissures\n\n")
        e.set_footer(text="The Void")
        for i, rift in enumerate(info):
            if len(info) > i + 1 and (
                    last_rift['tierNum'] != rift['tierNum']):
                e.add_field(
                    name='-=-=-=-=-=-=-=-=-',
                    value=f"__***{rift['tier']} {'Rifts' if not rift['isStorm'] else 'Void Storms'}***__",
                    inline=False)
                last_rift = rift

            if rift.setdefault('expired', None):
                # print(rift)
                continue
            node = re.sub(r"\)", r" Proxima)", rift['node']) if rift['isStorm'] else rift['node']
            e.add_field(
                name=f"{rift['missionType']}\n_{node}_",
                value=f"*{rift['eta']}*",
                inline=True)
        await ctx.respond(embed=e)
    else:
        await ctx.respond(
            "No void fissures are active. If you can read this, the API this bot uses is probably bugged out.")
        return


@plugin.command
@lightbulb.add_checks(lightbulb.human_only)
@lightbulb.option("item", "Item to search the market for (type at least 3 chars for autocompletion)", required=True, autocomplete=True)
@lightbulb.command("pricecheck", """Check prices of items on warframe.market""", aliases=["pc", "PC", "Pc", "pC"])
@lightbulb.implements(commands.SlashCommand, commands.PrefixCommand)
async def pricecheck(ctx):
    global wf_mkt_items
    global wf_mkt_last_update
    name = str(ctx.options.item).lower()
    if time.mktime(
            datetime.utcnow().timetuple()) > wf_mkt_last_update + 60 * 60 * 60 or not wf_mkt_items:
        wf_mkt_items = await get_item_info()
        wf_mkt_last_update = time.mktime(datetime.utcnow().timetuple())
        with open('data/wf_market_items.json', 'w') as file:
            json.dump({"items": wf_mkt_items, "last_update": wf_mkt_last_update}, file)
    fetchable_items = []
    for item in wf_mkt_items:
        # print(item)
        if item.get('url_name'):
            if name in item.get('item_name').lower() or name in item.get('url_name'):
                fetchable_items.append((item['item_name'], item['url_name']))
    if 1 < len(fetchable_items) < 15:
        msg = "Multiple items found. Did you mean:\n"
        for item in fetchable_items:
            msg += f"  `~ {item[0]}`?\n"
        await ctx.respond(msg)
        return
    elif len(fetchable_items) > 15:
        await ctx.respond(f"""
Search matched too many items.
Please be more specific.
(Found {len(fetchable_items)} items matching search)""")
    elif len(fetchable_items) < 1:
        await ctx.respond(f"""No item with name {name} found. Check spelling?""")
    else:
        for item_name, name in fetchable_items:
            try:
                item_stats, item_orders, item_info = await asyncio.gather(
                    *[get_item_statistics(name), get_item_orders(name), get_item_info(name)])
                item_info = [x for x in item_info['payload']['item']['items_in_set'] if x['url_name'] == name][0]
            except NameError as e:
                await ctx.respond(e)
                return

            for i in item_stats['include']['item']['items_in_set']:
                if item_stats['include']['item']['id'] == i['id']:
                    item = i
                    break

            two_days = item_stats['payload']['statistics_closed']['48hours']

            td_vol = []
            td_avg = []

            orders = item_orders['payload']['orders']

            buy = [order for order in orders if order['order_type'] == 'sell']
            buy.sort(key=lambda order: order['platinum'])
            buy_online = [item for item in buy if
                          item['user']['status'] == "online" or item['user']['status'] == "ingame"]

            sell = [order for order in orders if order['order_type'] == 'buy']
            sell.sort(key=lambda order: order['platinum'])
            sell_online = [order for order in sell if
                           order['user']['status'] == "online" or order['user']['status'] == "ingame"]

            for stat in two_days:
                rank = stat.setdefault('mod_rank', None)
                if not rank:
                    td_vol.append(stat['volume'])
                    td_avg.append(stat['avg_price'])
            vol = sum(td_vol)
            avg = sum(td_avg) / (len(td_avg) | 1)

            e = hikari.Embed()
            e.title = item_info['en']['item_name']
            e.url = 'https://warframe.market/items/' + item_info['url_name']
            e.set_author(name='Warframe.market price check')
            e.set_image('https://warframe.market/static/assets/' + item_info['icon'])
            e.set_footer(text='warframe.market')
            e.add_field("Average price (48hrs)", f"{round(avg)}p", inline=True)
            e.add_field("Trade Volume (48hrs)", f"{vol} items traded in the last 48hrs", inline=True)
            if item_info.get('ducats', None):
                e.add_field("Ducat/Plat Ratio", f"{round(int(item_info['ducats']) / avg, 1)} ducats per plat")
            else:
                e.add_field("-=-=-=-=-=-=-=-=-", f"-=-=-=-=-=-=-=-=-")
            if sell_online:
                e.add_field("Buy Offers", f"start at {int(sell_online[0]['platinum'])}p or less", inline=True)
            else:
                e.add_field("Buy Offers", "N/A (No offers from online players)", inline=True)
            if buy_online:
                e.add_field("Sell Offers", f"start at {int(buy_online[0]['platinum'])}p or more", inline=True)
            else:
                e.add_field("Sell Offers", "N/A (No offers from online players)", inline=True)

            await ctx.respond(embed=e)


@plugin.command
@lightbulb.add_checks(lightbulb.human_only)
@lightbulb.command("steelpath", """Lists all current Steel Path rewards""", aliases=['sp', 'steel'])
@lightbulb.implements(commands.SlashCommand, commands.PrefixCommand)
async def steelpath(ctx):
    """Lists all current Steel Path rewards"""

    async with aiohttp.ClientSession() as session:
        async with session.get('https://api.warframestat.us/pc/steelPath') as resp:
            info = await resp.json()

    e = hikari.Embed(title="Steel Path Rewards", description="All currently available Steel Path Rewards\n\n")
    e.set_footer(text="Teshin Dax")
    e.add_field('***Weekly Rotating Item***',
                f"{info['currentReward']['name']} ({info['currentReward']['cost']} Steel Essence)", inline=True)
    e.add_field("-=-=-=-=-=-=-=-=-", "***'Evergreen' Items***")

    for item in info['evergreens']:
        e.add_field(name=f"{item['name']}", value=f"({item['cost']} Steel Essence)", inline=True)
    await ctx.respond(embed=e)


@pricecheck.autocomplete('item')
async def pc_autocomp(opt: hikari.AutocompleteInteractionOption, autocomp):
    if len(opt.value) < 3:
        return 'Please type at least 3 characters'
    if wf_mkt_items:
        response = [item.get('item_name') for item in wf_mkt_items if opt.value.lower() in item.get('item_name').lower()]
        response.sort()
        if len(response) > 25:
            return response[:25]
        else:
            return response
    else:
        return 'Item Not Found'


def load(bot):
    bot.add_plugin(plugin)


def unload(bot):
    bot.remove_plugin(plugin)
