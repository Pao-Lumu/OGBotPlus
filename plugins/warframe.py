import asyncio
import json
# import pprint
import pprint
import random
import re
import time
from datetime import datetime

import aiohttp
import hikari
import lightbulb
import pytz


# from utils import helpers


class Warframe(lightbulb.Plugin):
    def __init__(self, bot):
        self.bot = bot
        try:
            with open('data/wf_market_items.json') as file:
                x = json.load(file)
                self.wf_mark_items = x['items']
                self.wf_mark_last_update = x['last_update']
        except (FileNotFoundError, json.JSONDecodeError):
            self.wf_mark_items = []
            self.wf_mark_last_update = 0
        super().__init__()

    @staticmethod
    async def fetch(session, url):
        async with session.get(url) as response:
            if response.status == 404:
                raise NameError('That is not a valid item. Please check your spelling.')
            else:
                return await response.text()

    async def get_items(self):
        async with aiohttp.ClientSession() as session:
            html = await self.fetch(session, f"https://api.warframe.market/v1/items")
            j = json.loads(html)['payload']['items']
            return j

    async def get_item_info(self, name):
        async with aiohttp.ClientSession() as session:
            html = await self.fetch(session, f"https://api.warframe.market/v1/items/{name}")
            j = json.loads(html)
            return j

    async def get_item_orders(self, name):
        async with aiohttp.ClientSession() as session:
            html = await self.fetch(session, f"https://api.warframe.market/v1/items/{name}/orders")
            j = json.loads(html)
            return j

    async def get_item_statistics(self, name):
        async with aiohttp.ClientSession() as session:
            html = await self.fetch(session, f"https://api.warframe.market/v1/items/{name}/statistics?include=item")
            j = json.loads(html)
            return j

    @lightbulb.check(lightbulb.human_only)
    @lightbulb.command(aliases=['when_baro'])
    async def baro(self, ctx):
        """Tells you where and when Baro Ki'Teer is coming, and what he's selling when he is here."""

        async with aiohttp.ClientSession() as session:
            async with session.get('https://api.warframestat.us/pc/voidTrader') as resp:
                info = await resp.json()

        hr_active = pytz.timezone('America/Chicago').fromutc(datetime.fromisoformat(info['activation'][:-1])) \
            .strftime("%A, %B %d, %Y at %I:%M %p %Z")
        hr_expiry = pytz.timezone('America/Chicago').fromutc(datetime.fromisoformat(info['expiry'][:-1])) \
            .strftime("%A, %B %d, %Y at %I:%M %p %Z")

        c = hikari.Colour.from_rgb(random.randint(0, 255), random.randint(0, 255), random.randint(0, 255))
        if not info['active']:
            e = hikari.Embed(title='Void Trader', color=c,
                             description="{} will arrive at {} on {} ({}) and will stay until {} ({})".format(
                                 info['character'], info['location'], hr_active, info['startString'], hr_expiry,
                                 info['endString']))
            await ctx.respond(embed=e)
        else:
            e = hikari.Embed(title="Void Trader Offerings", color=c)
            e.set_footer(text="Baro Ki'Teer")
            for offer in info['inventory']:
                e.add_field(name=offer['item'], value=f"{offer['ducats']} ducats + {offer['credits']} credits",
                            inline=True)

            dukey = "{0} is currently at {1}, and will leave on {2} {3}.".format(info['character'], info['location'],
                                                                                 hr_expiry, info['endString'])

            await ctx.respond(dukey, embed=e)

    @lightbulb.check(lightbulb.human_only)
    @lightbulb.command(aliases=['nw'])
    async def nightwave(self, ctx):
        """Lists all current Nightwave missions"""

        async with aiohttp.ClientSession() as session:
            async with session.get('https://api.warframestat.us/pc/nightwave') as resp:
                info = await resp.json()

        if info["active"]:
            e = hikari.Embed(title="Nightwave Challenges", description="All currently active Nightwave challenges\n\n")
            e.set_footer(text="Nora Night")

            for challenge in info['activeChallenges']:
                if 'isDaily' in challenge.keys() and challenge['isDaily']:
                    misson_type = "(Daily)"
                elif challenge['isElite']:
                    misson_type = "(Elite Weekly)"
                else:
                    misson_type = "(Weekly)"
                e.add_field(name=f" ~ {challenge['title']} {misson_type} ({challenge['reputation']} standing)",
                            value=f"~~ {challenge['desc']}")
            await ctx.respond(embed=e)
        else:
            await ctx.respond("Nightwave is currently inactive.")

    @lightbulb.check(lightbulb.human_only)
    @lightbulb.command(aliases=['voidrifts', 'rift', 'void'])
    async def rifts(self, ctx):
        """Lists all current void fissures"""
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
                        name='`~~~~~~~~~~~~~~~~~~~~~~~`',
                        value=f"***{rift['tier']} {'Rifts' if not rift['isStorm'] else 'Void Storms'}***",
                        inline=False)
                    last_rift = rift

                if rift.setdefault('expired', None):
                    print(rift)
                    continue
                node = re.sub(r"\)", r" Proxima)", rift['node']) if rift['isStorm'] else rift['node']
                e.add_field(
                    name=f"{rift['missionType']}\n_{node}_",
                    value=f"*{rift['eta']}*",
                    inline=True)
            await ctx.respond(embed=e)
        else:
            await ctx.respond(
                "No void storms are active. If you can read this, the API this bot uses is probably bugged out.")
            return

    @lightbulb.check(lightbulb.human_only)
    @lightbulb.command(aliases=["pc", "PC", "Pc", "pC"])
    @lightbulb.cooldown(5, 5, lightbulb.Bucket)
    async def pricecheck(self, ctx, *, item):
        """Check prices of items on warframe.market"""
        name = str(item).lower()
        if time.mktime(
                datetime.utcnow().timetuple()) > self.wf_mark_last_update + 60 * 60 * 60 or not self.wf_mark_items:
            self.wf_mark_items = await self.get_items()
            # pprint.pprint(self.wf_mark_items)
            self.wf_mark_last_update = time.mktime(datetime.utcnow().timetuple())
            with open('data/wf_market_items.json', 'w') as file:
                json.dump({"items": self.wf_mark_items, "last_update": self.wf_mark_last_update}, file)
        fetchable_items = []
        for item in self.wf_mark_items:
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
            await ctx.respond(f"""No item with that name found. Check spelling?""")
        else:
            pprint.pprint(fetchable_items)
            for item_name, name in fetchable_items:
                try:
                    item_stats, item_orders, item_info = await asyncio.gather(
                        *[self.get_item_statistics(name), self.get_item_orders(name), self.get_item_info(name)])
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
                avg = sum(td_avg) / len(td_avg)

                e = hikari.Embed()
                e.title = item['en']['item_name']
                e.url = 'https://warframe.market/items/' + item['url_name']
                e.set_author(name='Warframe.market price check')
                e.set_image('https://warframe.market/static/assets/' + item['icon'])
                e.set_footer(text='warframe.market')
                e.add_field("Average price (48hrs)", f"{round(avg)}p", inline=True)
                e.add_field("Trade Volume (48hrs)", f"{vol} items traded in the last 48hrs", inline=True)
                if not 'set' in item['url_name']:
                    e.add_field("Ducat/Plat Ratio", f"{round(int(item_info['ducats'])/avg, 1)} ducats per plat")
                else:
                    e.add_field("-=-=-=-=-=-=-=-=-", f"-=-=-=-=-=-=-=-=-")
                e.add_field("Buy Offers", f"start at {int(sell_online[0]['platinum'])}p or less", inline=True)
                e.add_field("Sell Offers", f"start at {int(buy_online[0]['platinum'])}p or more", inline=True)

                # e.description = f"""{vol} {item['en']['item_name']} sold in the past 48hrs, for {round(avg)}p on average.
                # Active Buy Orders start at {int(sell_online[0]['platinum'])}p or less.
                # Active Sell Orders start at {int(buy_online[0]['platinum'])}p or more."""

                await ctx.respond(embed=e)

    @lightbulb.check(lightbulb.human_only)
    @lightbulb.command(aliases=['sp', 'steel'])
    async def steelpath(self, ctx):
        """Lists all current Steel Path rewards"""

        async with aiohttp.ClientSession() as session:
            async with session.get('https://api.warframestat.us/pc/steelPath') as resp:
                info = await resp.json()

        e = hikari.Embed(title="Steel Path Rewards", description="All currently available Steel Path Rewards\n\n")
        e.set_footer(text="God King Teshin")
        e.add_field('***Weekly Rotating Item***',
                    f"{info['currentReward']['name']} ({info['currentReward']['cost']} Steel Essence)", inline=True)
        e.add_field("`~~~~~~~~~~~~~~~~~~~~~~~~`", "***'Evergreen' Items***")

        for item in info['evergreens']:
            e.add_field(name=f"{item['name']}", value=f"({item['cost']} Steel Essence)", inline=True)
        await ctx.respond(embed=e)
