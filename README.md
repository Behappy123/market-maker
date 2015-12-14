BitMEX Market Maker
===================

This is a sample market making bot for use with [BitMEX](https://testnet.bitmex.com).

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
1. Satisfied with your bot's performance? Create a [live API Key](https://testnet.bitmex.com/app/apiKeys) for your
   BitMEX account, set the `BASE_URL` and start trading!


Compatibility
-------------

This module is compatible with both Python 2 and 3 using Python's `future` module.

Some helpful tips on Py2/3 compatibility: http://python-future.org/compatible_idioms.html
