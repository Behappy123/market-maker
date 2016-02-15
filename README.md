BitMEX Market Maker
===================

This is a sample market making bot for use with [BitMEX](https://www.bitmex.com).

It is free to use and modify for your own strategies. It provides the following:

* A `BitMEX` object wrapping the REST and WebSocket APIs.
  * All data is realtime and efficiently [fetched via the WebSocket](market_maker/ws/ws_thread.py). This is the fastest way to get market data.
  * Orders may be created, queried, and cancelled via `BitMEX.buy()`, `BitMEX.sell()`, `BitMEX.open_orders()` and the like.
  * Withdrawals may be requested (but they still must be confirmed via email and 2FA).
  * Connection errors and WebSocket reconnection is handled for you.
  * [Permanent API Key](https://testnet.bitmex.com/app/apiKeys) support is included.
* A scaffolding for building your own trading strategies.
  * Out of the box, a simple market making strategy is implemented that blankets the bid and ask.
    to tune it.
  * More complicated strategies are up to the user. Try incorporating [index data](https://testnet.bitmex.com/app/index/.XBT),
    query other markets to catch moves early, or develop your own completely custom strategy.

**Develop on [Testnet](https://testnet.bitmex.com) first!** Testnet trading is completely free and is identical to the live market.

Getting Started
---------------

1. Create a [Testnet BitMEX Account](https://testnet.bitmex.com) and [deposit some TBTC](https://testnet.bitmex.com/app/deposit).
1. Get dependencies: `python setup.py install`
  * This will create a `settings.py` file at the root. Modify this file to tune parameters.
1. Edit settings.py to add your BitMEX username and password and change bot parameters.
  * Run with DRY_RUN=True to test cost and spread.
1. Run it: `./marketmaker [symbol]`
1. Want faster authentication? Create [an API Key](https://testnet.bitmex.com/app/apiKeys)
1. Satisfied with your bot's performance? Create a [live API Key](https://www.bitmex.com/app/apiKeys) for your
   BitMEX account, set the `BASE_URL` and start trading!

Operation Overview
------------------

This market maker works on the following principles:

* The MM tracks the last bidPrice and askPrice of the quoted instrument to determine where to start quoting.
* Based on parameters set the user, the bot creates a descriptions of orders it would like to place.
  - If settings.MAINTAIN_SPREADS is set, the bot will start inside the current spread and work outwards.
  - Otherwise, spread is determined by interval calculations.
* If the user specified position limits, these are checked. If the current position is beyond a limit,
  the bot stops quoting that side of the market.
* These order descriptors are compared with what the bot has currently placed in the market.
  - If an existing order can be amended to the desired value, it is amended.
  - Otherwise, a new order is created.
  - Extra orders are canceled.
* The bot then prints details of contracts traded, tickers, and total delta.

Simplified Output
-----------------

The following is some of what you can expect when running this bot:

```
2016-01-28 17:29:31,054 - INFO - market_maker - BitMEX Market Maker Version: 1.0
2016-01-28 17:29:31,074 - INFO - ws_thread - Connecting to wss://testnet.bitmex.com/realtime?subscribe=quote:XBT7D,trade:XBT7D,instrument,order:XBT7D,execution:XBT7D,margin,position
2016-01-28 17:29:31,074 - INFO - ws_thread - Authenticating with API Key.
2016-01-28 17:29:31,075 - INFO - ws_thread - Started thread
2016-01-28 17:29:32,079 - INFO - ws_thread - Connected to WS. Waiting for data images, this may take a moment...
2016-01-28 17:29:32,079 - INFO - ws_thread - Got all market data. Starting.
2016-01-28 17:29:32,079 - INFO - market_maker - Using symbol XBT7D.
2016-01-28 17:29:32,079 - INFO - market_maker - Order Manager initializing, connecting to BitMEX. Live run: executing real trades.
2016-01-28 17:29:32,079 - INFO - market_maker - Resetting current position. Cancelling all existing orders.
2016-01-28 17:29:33,460 - INFO - market_maker - XBT7D Ticker: Buy: 388.61, Sell: 389.89
2016-01-28 17:29:33,461 - INFO - market_maker - Start Positions: Buy: 388.62, Sell: 389.88, Mid: 389.25
2016-01-28 17:29:33,461 - INFO - market_maker - Current XBT Balance: 3.443498
2016-01-28 17:29:33,461 - INFO - market_maker - Current Contract Position: -1
2016-01-28 17:29:33,461 - INFO - market_maker - Avg Cost Price: 389.75
2016-01-28 17:29:33,461 - INFO - market_maker - Avg Entry Price: 389.75
2016-01-28 17:29:33,462 - INFO - market_maker - Contracts Traded This Run: 0
2016-01-28 17:29:33,462 - INFO - market_maker - Total Contract Delta: -17.7510 XBT
2016-01-28 17:29:33,462 - INFO - market_maker - Creating 4 orders:
2016-01-28 17:29:33,462 - INFO - market_maker - Sell 100 @ 389.88
2016-01-28 17:29:33,462 - INFO - market_maker - Sell 200 @ 390.27
2016-01-28 17:29:33,463 - INFO - market_maker -  Buy 100 @ 388.62
2016-01-28 17:29:33,463 - INFO - market_maker -  Buy 200 @ 388.23
-----
2016-01-28 17:29:37,366 - INFO - ws_thread - Execution: Sell 1 Contracts of XBT7D at 389.88
2016-01-28 17:29:38,943 - INFO - market_maker - XBT7D Ticker: Buy: 388.62, Sell: 389.88
2016-01-28 17:29:38,943 - INFO - market_maker - Start Positions: Buy: 388.62, Sell: 389.88, Mid: 389.25
2016-01-28 17:29:38,944 - INFO - market_maker - Current XBT Balance: 3.443496
2016-01-28 17:29:38,944 - INFO - market_maker - Current Contract Position: -2
2016-01-28 17:29:38,944 - INFO - market_maker - Avg Cost Price: 389.75
2016-01-28 17:29:38,944 - INFO - market_maker - Avg Entry Price: 389.75
2016-01-28 17:29:38,944 - INFO - market_maker - Contracts Traded This Run: -1
2016-01-28 17:29:38,944 - INFO - market_maker - Total Contract Delta: -17.7510 XBT
2016-01-28 17:29:38,945 - INFO - market_maker - Amending Sell: 99 @ 389.88 to 100 @ 389.88 (+0.00)

```


Notes on Rate Limiting
----------------------

By default, the BitMEX API rate limit is 300 requests per 5 minute interval (avg 1/second).

This bot uses the WebSocket and bulk order placement/amend to greatly reduce the number of calls sent to the BitMEX API.

Most calls to the API consume one request, except:

* Bulk order placement/amend: Consumes 0.5 requests, rounded up, per order. For example, placing 9 orders consumes
  5 requests.
* Bulk order cancel: Consumes 1 request no matter the size. Is not blocked by an exceeded ratelimit; cancels will
  always succeed. This bot will always cancel all orders on an error or interrupt.

If you are quoting multiple contracts and your ratelimit is becoming an obstacle, please
[email support](mailto:support@bitmex.com) with details of your quoting. In the vast majority of cases,
we are able to raise a user's ratelimit without issue.


Compatibility
-------------

This module is compatible with both Python 2 and 3 using Python's `future` module.

Some helpful tips on Py2/3 compatibility: http://python-future.org/compatible_idioms.html
