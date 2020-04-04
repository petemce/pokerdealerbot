import os
import logging
import asyncio
import ssl as ssl_lib

import certifi
import slack
import random
import itertools
from collections import OrderedDict
from treys import Deck
from treys import Evaluator
from treys import Card


player_list = {}
tab_list = {}
newMoney = 20000
bigblind = 200
smallblind = bigblind / 2


class Player(object):
    def __init__(self, newName, newMoney):
        self.name = newName
        self.money = newMoney
        self.bet = 0
        self.cards = []
        self.dealer = False
        self.fold = False
        self.sidepotsize = 0
        self.tocall = 0
        self.reraise = 0
        self.canclose = False
        self.cardswords = None
        self.score = 0


class Table(object):
    def __init__(self):
        self.bet = 0
        self.turn = 0
        self.cards = []
        self.pot = 0
        self.sidepot = 0
        self.highbet = 0
        self.plo = False
        self.origlist = []


async def sendslack(text, web_client: slack.WebClient, channel):
    await web_client.chat_postMessage(
        channel=channel, icon_emoji=":robot_face:", username="pokerbot", text=text
    )
    print("ok")


async def create_player_list(web_client, user_id, channel_id, num_players, plo=False):
    num_players = int(num_players)
    if channel_id not in player_list:
        player = Player(user_id, newMoney)
        player_list[channel_id] = []
        player_list[channel_id].append(player)
        print("added %s to list" % user_id)
        print(len(player_list[channel_id]))

    elif user_id not in player_list[channel_id]:
        player = Player(user_id, newMoney)
        player_list[channel_id].append(player)
        if len(player_list[channel_id]) == num_players:
            if plo:
                print("setting uo plo")
                await set_up_game(web_client, channel_id, plo=True)
            else:
                await set_up_game(web_client, channel_id, plo=False)
            print("added %s to list - 1" % user_id)
            print(len(player_list[channel_id]))

    elif (
        user_id not in player_list[channel_id]
        and len(player_list[channel_id]) > num_players
    ):
        player = Player(user_id, newMoney)
        player_list[channel_id].append(player)
        # await set_up_game(web_client, channel_id)
        print("added %s to list - 2" % user_id)
        print(len(player_list[channel_id]))


async def set_up_game(web_client, channel_id, plo=False):
    players = player_list[channel_id]
    if channel_id not in tab_list:
        deck = Deck()
        deck.shuffle()
        tab = Table()
        tab_list[channel_id] = {}
        tab_list[channel_id]["table"] = tab
        tab_list[channel_id]["deck"] = deck
    tab = tab_list[channel_id]["table"]
    deck = tab_list[channel_id]["deck"]
    deck.shuffle()
    tab.cards.extend(deck.draw(3))
    if plo:
        print("plos")
        tab.plo = True
    for name in players:
        if plo:
            name.cards.extend(deck.draw(4))
        else:
            print("nlhe")
            name.cards.extend(deck.draw(2))
        print("got to cards bit")
        pic = Card.print_pretty_cards(name.cards)
        await sendslack(pic, web_client, name.name)

    if len(players) == 2:
        i = random.randint(1, 2)
        if i == 1:
            players += [players.pop(0)]
        await start_heads_up(web_client, channel_id)

    if len(players) > 2:
        random.shuffle(players)
        tab.origlist = players.copy()
        await start_game(web_client, channel_id)


async def start_game(web_client, channel_id):
    players = player_list[channel_id]
    tab = tab_list[channel_id]["table"]
    print("starting game ")
    await sendslack("Starting new game...", web_client, channel_id)
    await sendslack("Starting stacks are %d" % newMoney, web_client, channel_id)
    await sendslack(
        "Big blind is %d, small blind is %d" % (bigblind, smallblind),
        web_client,
        channel_id,
    )
    players[0].money = players[1].money - smallblind
    players[0].tocall = smallblind
    players[1].bet = bigblind
    players[1].money = players[1].money - bigblind
    players[1].canclose = True
    players[-1].dealer = True
    tab.pot = tab.pot + players[1].bet + players[2].bet
    tab.highbet = bigblind
    #if not first game
    if len(players) == 3:
        order = [2, 0, 1]
        players = [players[i] for i in order]

    elif len(players) == 4:
        order = [3, 2, 0, 1 ]
        players = [players[i] for i in order]

    elif len(players) == 5:
        order = [4, 3, 2, 0, 1]
        players = [players[i] for i in order]

    elif len(players) == 6:
        order = [5, 4, 3, 2, 0, 1]
        players = [players[i] for i in order]

    await sendslack(
        "<@%s> is first to act" % players[0].name, web_client, channel_id
    )
    await sendslack("%d to call" % bigblind, web_client, channel_id)


async def start_heads_up(web_client, channel_id):
    active_players = player_list[channel_id]
    tab = tab_list[channel_id]["table"]
    print("starting heads up")
    await sendslack("Starting new heads up game...", web_client, channel_id)
    for name in active_players:
        await sendslack(
            "<@%s> has %d" % (name.name, name.money), web_client, channel_id
        )

    await sendslack(
        "Big blind is %d, small blind is %d" % (bigblind, smallblind),
        web_client,
        channel_id,
    )
    active_players[0].bet = smallblind
    active_players[0].money = active_players[0].money - smallblind
    active_players[0].tocall = smallblind
    active_players[1].dealer = True
    active_players[1].bet = bigblind
    active_players[1].canclose = True
    active_players[1].money = active_players[1].money - bigblind
    tab.pot = tab.pot + active_players[0].bet + active_players[1].bet
    tab.highbet = smallblind
    await sendslack(
        "<@%s> is first to act" % active_players[0].name, web_client, channel_id
    )
    await sendslack("%d to call" % smallblind, web_client, channel_id)


async def handle_fold(web_client, text, user_id, channel_id):
    print("handling fold")
    active_players = player_list[channel_id]
    tab = tab_list[channel_id]["table"]
    print(tab.plo)
    if active_players[0].name == user_id:
        active_players[1].money += tab.pot
        if active_players[0].money != 0 and active_players[1].money != 0 and len(active_players) == 2:
            await sendslack(
                "<@%s> folds" % active_players[0].name, web_client, channel_id
            )
            await sendslack(
                "<@%s> wins %d" % (active_players[1].name, tab.pot),
                web_client,
                channel_id,
            )
            if active_players[1].dealer:
                active_players[1].dealer = False
                active_players += [active_players.pop(0)]
            tab.cards.clear()
            tab.pot = 0
            tab.turn = 0
            tab.highbet = 0
            for name in active_players:
                name.cards.clear()
                name.tocall = 0
                name.canclose = False
                name.bet = 0
                name.dealer = False
                name.reraise = 0

            if tab.plo:
                print("setting up", tab.plo)
                await set_up_game(web_client, channel_id, plo=True)
            else:
                await set_up_game(web_client, channel_id, plo=False)

        elif 


async def handle_bet(web_client, text, user_id, channel_id, amount):
    active_players = player_list[channel_id]
    bet = int(amount)
    print(bet)
    tab = tab_list[channel_id]["table"]
    print(tab.highbet)
    for name in active_players:
        print(name.name)
    print(len(active_players))
    if active_players[0].name == user_id:
        print("received bet for %d from %s" % (bet, user_id))
        print(active_players[0].canclose, "pish")
        if (
            bet >= 1
            and bet <= 199
            and active_players[0].money > bet
            and not bet == active_players[0].tocall
        ):
            await sendslack(
                "bet must be equal or higher than %d" % tab.highbet,
                web_client,
                channel_id,
            )
            await sendslack(
                "<@%s> is next to act, %d to call "
                % (active_players[0].name, tab.highbet),
                web_client,
                channel_id,
            )
            return

        elif (
            active_players[0].canclose
            and bet == tab.highbet
            or bet == active_players[0].money
        ):
            print("bollocks")
            await bet_to_close(web_client, user_id, channel_id, bet)
            return

        await bet_to_continue(web_client, user_id, channel_id, bet)


async def bet_to_continue(web_client, user_id, channel_id, bet):
    active_players = player_list[channel_id]
    tab = tab_list[channel_id]["table"]
    if bet == 0 and tab.highbet == 0:
        print("heck")
        await sendslack("<@%s> checks" % active_players[0].name, web_client, channel_id)
        await sendslack(
            "<@%s> is next to act" % active_players[1].name, web_client, channel_id
        )
        await sendslack("pot is %s" % tab.pot, web_client, channel_id)
        tab.highbet = 0
        active_players += [active_players.pop(0)]
        return

    elif bet > tab.highbet:
        if active_players[0].money > bet:
            print(tab.highbet)
            print("fg")
            print(active_players[0].bet)
            print(active_players[0].tocall)
            print(active_players[1].bet)
            print(active_players[1].tocall)
            print("hj")
            tab.pot += bet
            if active_players[0].tocall != 0:
                print("boogie")
                print(active_players[0].reraise, "jame")
                active_players[0].reraise = bet - active_players[0].tocall
                print(active_players[0].reraise, "bmn")
                tab.highbet = active_players[0].reraise
                active_players[0].tocall = 0
                active_players[0].money = active_players[0].money - bet
                active_players[0].bet = active_players[0].reraise
                active_players[1].tocall = active_players[0].bet
                active_players[-1].canclose = True
                await sendslack(
                    "<@%s> is next to act" % active_players[1].name,
                    web_client,
                    channel_id,
                )
                await sendslack("%d to call" % tab.highbet, web_client, channel_id)
                await sendslack("pot is %s" % tab.pot, web_client, channel_id)
                active_players += [active_players.pop(0)]
                return

            print(bet, active_players[0].bet, active_players[1].bet)
            print(tab.highbet, "gah")
            tab.highbet = bet - active_players[1].bet
            print(tab.highbet, "boom")
            active_players[0].bet = bet - active_players[0].bet
            active_players[0].money = active_players[0].money - bet
            active_players[0].tocall = 0
            active_players[1].tocall = tab.highbet
            print(type(active_players[1].name))
            print(type(web_client))
            print(type(channel_id))
            print("fiddle")
            await sendslack(
                "<@%s> is next to act" % active_players[1].name, web_client, channel_id
            )
            await sendslack("%d to call" % tab.highbet, web_client, channel_id)
            await sendslack("pot is %s" % tab.pot, web_client, channel_id)
            active_players += [active_players.pop(0)]
            active_players[0].canclose = True
            return

    elif bet == tab.highbet:
        tab.pot += bet
        tab.highbet = 0
        active_players[0].bet = 0
        print("turnzerofuncnobet")
        active_players[0].money = active_players[0].money - bet
        active_players[1].tocall = 0
        # active_players[1].bet = 0
        await sendslack(
            "<@%s> is next to act" % active_players[1].name, web_client, channel_id
        )
        await sendslack("%d is minimum bet" % tab.highbet, web_client, channel_id)
        await sendslack("pot is %s" % tab.pot, web_client, channel_id)
        active_players += [active_players.pop(0)]
        return


async def handle_allin(web_client, text, user_id, channel_id, amount):
    active_players = player_list[channel_id]
    tab = tab_list[channel_id]["table"]
    if active_players[0].name == user_id:
        if not active_players[0].allin:
            this
        tab.highbet = tab.pot + active_players[0].money

        await sendslack("<@%s> is all in" % tab.highbet, web_client, channel_id)


async def bet_to_close(web_client, user_id, channel_id, bet):
    active_players = player_list[channel_id]
    tab = tab_list[channel_id]["table"]
    deck = tab_list[channel_id]["deck"]
    if bet == tab.highbet:

        print("betwixt")
        tab.pot += bet
        active_players[0].money = active_players[0].money - bet
        print(active_players[0].money, "active")
        print(active_players[1].money, "notactive")
        if tab.turn == 0:
            print("stage5")
            tabcards = Card.print_pretty_cards(tab.cards)
            await sendslack(
                "<@%s> calls. dealing flop:" % user_id, web_client, channel_id
            )
            await sendslack(tabcards, web_client, channel_id)
            if active_players[0].dealer:
                active_players += [active_players.pop(0)]

            await sendslack(
                "<@%s> is next to act" % active_players[0].name, web_client, channel_id
            )
            await sendslack("pot is %s" % tab.pot, web_client, channel_id)
            for name in active_players:
                name.bet = 0
                name.tocall = 0
                name.reraise = 0
            tab.turn += 1
            tab.highbet = 0
            active_players[0].canclose = False
            active_players[1].canclose = True

        elif tab.turn == 1:
            print("stage6")
            tab.cards.append(deck.draw(1))
            print(tab_list[channel_id]["table"].cards)
            tabcards = Card.print_pretty_cards(tab.cards)
            await sendslack(
                "<@%s> calls. dealing turn:" % user_id, web_client, channel_id
            )
            await sendslack(tabcards, web_client, channel_id)
            if active_players[0].dealer:
                active_players += [active_players.pop(0)]

            await sendslack(
                "<@%s> is next to act" % active_players[0].name, web_client, channel_id
            )
            await sendslack("pot is %s" % tab.pot, web_client, channel_id)
            for name in active_players:
                name.bet = 0
                name.tocall = 0
                name.reraise = 0
            tab.turn += 1
            tab.highbet = 0
            active_players[0].canclose = False
            active_players[1].canclose = True

        elif tab.turn == 2:
            print("stage7")
            tab.cards.append(deck.draw(1))
            print(tab.cards)
            tabcards = Card.print_pretty_cards(tab.cards)
            await sendslack(
                "<@%s> calls. dealing river:" % user_id, web_client, channel_id
            )
            await sendslack(tabcards, web_client, channel_id)
            if active_players[0].dealer:
                active_players += [active_players.pop(0)]

            await sendslack(
                "<@%s> is next to act" % active_players[0].name, web_client, channel_id
            )
            await sendslack("pot is %s" % tab.pot, web_client, channel_id)

            for name in active_players:
                name.bet = 0
                name.tocall = 0
                name.reraise = 0
            tab.turn += 1
            tab.highbet = 0
            active_players[0].canclose = False
            active_players[1].canclose = True

        elif tab.turn == 3:
            await sendslack("<@%s> calls." % user_id, web_client, channel_id)
            tabcards = Card.print_pretty_cards(tab.cards)
            await sendslack(tabcards, web_client, channel_id)
            if tab.plo == True:
                await calculate_plo(web_client, user_id, channel_id)
            else:
                # players = player_list[channel_id]
                evaluator = Evaluator()
                scores = {}
                for p in active_players:
                    pic = Card.print_pretty_cards(p.cards)
                    await sendslack(
                        "<@%s> has %s" % (p.name, pic), web_client, channel_id
                    )
                    scores[evaluator.evaluate(tab.cards, p.cards)] = p
                    p.cards = []

                d = OrderedDict(sorted(scores.items(), key=lambda t: t[0]))
                items = list(d.items())
                for i in items:
                    print(i, "herewith")
                    p_score = i[0]
                    p_class = evaluator.get_rank_class(p_score)
                    hand = evaluator.class_to_string(p_class)
                    await sendslack(
                        "<@%s> has %s" % (i[1].name, hand), web_client, channel_id
                    )
                winner = [x for x in items if x[0] == items[0][0]]

                for p in winner:
                    await sendslack(
                        "<@%s> won and got %d" % (p[1].name, tab.pot),
                        web_client,
                        channel_id,
                    )
                    for name in active_players:
                        if name.name == p[1].name:
                            name.money += tab.pot

                if len(active_players) == 2:
                    if active_players[0].money != 0 and active_players[1].money != 0:
                        if active_players[1].dealer:
                            active_players += [active_players.pop(0)]

                        tab.cards.clear()
                        tab.turn = 0
                        tab.highbet = 0
                        tab.pot = 0
                        for name in active_players:
                            name.cards.clear()
                            name.tocall = 0
                            name.dealer = False
                            name.bet = 0
                            name.reraise = 0
                            name.canclose = False
                        await set_up_game(web_client, channel_id)


async def find_best_plo_hand(user_id, channel_id):
    active_players = player_list[channel_id]
    tab = tab_list[channel_id]["table"]
    evaluator = Evaluator()
    board = tab.cards
    print(board, "board")
    hand = [x.cards for x in active_players if x.name == user_id]
    hand = hand[0]
    print(hand, "hand")
    allboardtuple = list(itertools.combinations(board, 3))
    print(allboardtuple)
    allboardlist = [list(x) for x in allboardtuple]
    print(allboardlist)
    allhandtuple = list(itertools.combinations(hand, 2))
    print(allhandtuple, "allhandtuple")
    allhandlist = [list(x) for x in allhandtuple]
    print(allhandlist, "allhandlist")
    fullsetlist = []
    print("just before loop")
    for i in allboardlist:
        print(i, "inside loop i")
        for j in allhandlist:
            print(j, "inside loop j")
            fullsetlist.append(evaluator.evaluate(i, j))
    # for allboardlist, allhandlist in zip(allboardlist, allhandlist):
    #   fullsetlist.append(evaluator.evaluate(allboardlist, allhandlist))

    fullsetlist.sort()
    return fullsetlist[0]


async def calculate_plo(web_client, user_id, channel_id):
    active_players = player_list[channel_id]
    tab = tab_list[channel_id]["table"]
    evaluator = Evaluator()

    for name in active_players:
        high = await find_best_plo_hand(name.name, channel_id)
        print(high, name.name)
        rank = evaluator.get_rank_class(high)
        name.cardswords = evaluator.class_to_string(rank)
        name.score = high

    for name in active_players:
        pic = Card.print_pretty_cards(name.cards)
        await sendslack("<@%s> shows %s" % (name.name, pic), web_client, channel_id)

    for name in active_players:
        await sendslack(
            "<@%s> has %s" % (name.name, name.cardswords), web_client, channel_id
        )

    if active_players[0].score < active_players[1].score:
        await sendslack(
            "<@%s> wins %d" % (active_players[0].name, tab.pot), web_client, channel_id
        )
        active_players[0].money += tab.pot

    else:
        await sendslack(
            "<@%s> wins %d" % (active_players[1].name, tab.pot), web_client, channel_id
        )
        active_players[1].money += tab.pot

    if len(active_players) > 1:
        if active_players[0].money != 0 and active_players[1].money != 0:
            if active_players[1].dealer:
                active_players += [active_players.pop(0)]

            tab.cards.clear()
            tab.turn = 0
            tab.highbet = 0
            tab.pot = 0
            for name in active_players:
                name.cards.clear()
                name.tocall = 0
                name.dealer = False
                name.bet = 0
                name.reraise = 0
                name.canclose = False
            await set_up_game(web_client, channel_id, plo=True)


# Listen for message events
@slack.RTMClient.run_on(event="message")
async def message(**payload):
    """Listen for message
    """
    data = payload["data"]
    web_client = payload["web_client"]
    channel_id = data.get("channel")
    user_id = data.get("user")
    if text is None:
        return
    test = text.lower()
    if text.startswith("start game"):
        resp = text.split(" ")
        if len(resp) == 3 and resp[2].isdigit():
            return await create_player_list(
                web_client, user_id, channel_id, resp[2], plo=False
            )
        return await sendslack(
            'Please use "start game N", with N being number of players',
            web_client,
            channel_id,
        )

    if text.startswith("start plo"):
        resp = text.split(" ")
        if len(resp) == 3 and resp[2].isdigit():
            return await create_player_list(
                web_client, user_id, channel_id, resp[2], plo=True
            )

    if text.startswith("bet"):
        resp = text.split(" ")
        if len(resp) == 2 and resp[1].isdigit():
            return await handle_bet(web_client, text, user_id, channel_id, resp[1])

    if text == "fold":
        return await handle_fold(web_client, text, user_id, channel_id)


if __name__ == "__main__":
    logger = logging.getLogger()
    logger.setLevel(logging.DEBUG)
    logger.addHandler(logging.StreamHandler())
    ssl_context = ssl_lib.create_default_context(cafile=certifi.where())
    slack_token = os.environ["SLACK_BOT_TOKEN"]
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    rtm_client = slack.RTMClient(
        token=slack_token, ssl=ssl_context, run_async=True, loop=loop
    )
    loop.run_until_complete(rtm_client.start())
