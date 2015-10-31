from __future__ import absolute_import
from time import sleep
import sys
from datetime import datetime
from os.path import getmtime
import string
import atexit

from market_maker import bitmex
from market_maker.settings import settings
from market_maker.utils import log, constants, errors

# Used for reloading the bot - saves modified times of key files
import os
watched_files_mtimes = [(f, getmtime(f)) for f in settings.WATCHED_FILES]


#
# Helpers
#
logger = log.setup_custom_logger('root')


class ExchangeInterface:
    def __init__(self, dry_run=False):
        self.dry_run = dry_run
        if len(sys.argv) > 1:
            self.symbol = sys.argv[1]
        else:
            self.symbol = settings.SYMBOL
        self.bitmex = bitmex.BitMEX(base_url=settings.BASE_URL, symbol=self.symbol, login=settings.LOGIN,
                                    password=settings.PASSWORD, otpToken=settings.OTPTOKEN, apiKey=settings.API_KEY,
                                    apiSecret=settings.API_SECRET, orderIDPrefix=settings.ORDERID_PREFIX)

    def authenticate(self):
        if not self.dry_run:
            self.bitmex.authenticate()

    def cancel_order(self, order):
        logger.info("Cancelling: %s %d @ %.2f" % (order['side'], order['orderQty'], "@", order['price']))
        while True:
            try:
                self.bitmex.cancel(order['orderID'])
                sleep(settings.API_REST_INTERVAL)
            except ValueError as e:
                logger.info(e)
                sleep(settings.API_ERROR_INTERVAL)
            else:
                break

    def cancel_all_orders(self):
        if self.dry_run:
            return

        logger.info("Resetting current position. Cancelling all existing orders.")

        # In certain cases, a WS update might not make it through before we call this.
        # For that reason, we grab via HTTP to ensure we grab them all.
        orders = self.bitmex.http_open_orders()

        for order in orders:
            logger.info("Cancelling: %s %d @ %.2f" % (order['side'], order['orderQty'], order['price']))

        if len(orders):
            self.bitmex.cancel([order['orderID'] for order in orders])

        sleep(settings.API_REST_INTERVAL)

    def get_instrument(self):
        return self.bitmex.get_instrument()

    def get_ticker(self):
        return self.bitmex.ticker_data()

    def get_trade_data(self):
        if self.dry_run:
            margin = {'marginBalance': float(settings.DRY_BTC), 'availableFunds': float(settings.DRY_BTC)}
            orders = []
        else:
            orders = self.bitmex.open_orders()
            margin = self.bitmex.funds()

        return {"margin": margin, "orders": orders}

    def is_open(self):
        """Check that websockets are still open."""
        return not self.bitmex.ws.exited

    def place_order(self, price, quantity, order_type):
        if settings.DRY_RUN:
            return {'orderID': 'dry_run_order', 'orderQty': quantity, 'price': price, 'symbol': self.symbol}

        if order_type == "Buy":
            order = self.bitmex.buy(quantity, price)
        elif order_type == "Sell":
            order = self.bitmex.sell(quantity, price)
        else:
            logger.error("Invalid order type")
            sys.exit()

        return order


class OrderManager:
    def __init__(self):
        self.exchange = ExchangeInterface(settings.DRY_RUN)
        # Once exchange is created, register exit handler that will always cancel orders
        # on any error.
        atexit.register(self.exit)

        logger.info("Using symbol %s." % self.exchange.symbol)

    def init(self):
        if settings.DRY_RUN:
            logger.info("Initializing dry run. Orders printed below represent what would be posted to BitMEX.")
        else:
            logger.info("Order Manager initializing, connecting to BitMEX. Live run: executing real trades.")
        self.exchange.authenticate()
        self.start_time = datetime.now()
        self.instrument = self.exchange.get_instrument()
        self.reset()

    def reset(self):
        self.exchange.cancel_all_orders()
        # We keep our own orders cache that allows us to reconcile what the exchange says we have open,
        # and what we believed we had open.
        self.orders = {}

        ticker = self.get_ticker()

        trade_data = self.exchange.get_trade_data()
        self.start_XBt = trade_data["margin"]["marginBalance"]
        logger.info("Current XBT Balance: %.6f" % XBt_to_XBT(self.start_XBt))

        # Sanity check:
        if self.get_position(-1) >= ticker["sell"] or self.get_position(1) <= ticker["buy"]:
            logger.error(self.start_position_mid)
            logger.error("%s %s %s %s" % (self.get_position(-1), ticker["sell"], self.get_position(1), ticker["buy"]))
            logger.error("Sanity check failed, exchange data is screwy")
            sys.exit()

        for i in range(1, settings.ORDER_PAIRS + 1):
            self.place_order(-i, "Buy")
            self.place_order(i, "Sell")

        if settings.DRY_RUN:
            sys.exit()

    def get_ticker(self):
        ticker = self.exchange.get_ticker()
        # Set up our buy & sell positions as the smallest possible unit above and below the current spread
        # and we'll work out from there. That way we always have the best price but we don't kill wide
        # and potentially profitable spreads.
        self.start_position_buy = ticker["buy"] + self.instrument['tickSize']
        self.start_position_sell = ticker["sell"] - self.instrument['tickSize']

        # Back off if our spread is too small.
        if self.start_position_buy * (1.00 + settings.MIN_SPREAD) > self.start_position_sell:
            self.start_position_buy *= (1.00 - (settings.MIN_SPREAD / 2))
            self.start_position_sell *= (1.00 + (settings.MIN_SPREAD / 2))

        # Midpoint, used for simpler order placement.
        self.start_position_mid = ticker["mid"]
        logger.info(
            "%s Ticker: Buy: %.2f, Sell: %.2f" %
            (self.instrument['symbol'], ticker["buy"], ticker["sell"])
        )
        logger.info('Start Positions: Buy: %.2f, Sell: %.2f, Mid: %.2f' %
                    (self.start_position_buy, self.start_position_sell, self.start_position_mid))
        return ticker

    def get_position(self, index):
        # Maintain existing spreads for max profit
        if settings.MAINTAIN_SPREADS:
            start_position = self.start_position_buy if index < 0 else self.start_position_sell
            # First positions (index 1, -1) should start right at start_position, others should branch from there
            index = index + 1 if index < 0 else index - 1
        else:
            start_position = self.start_position_mid
        return round(start_position * (1 + settings.INTERVAL)**index, self.instrument['tickLog'])

    def place_order(self, index, order_type):
        position = self.get_position(index)

        quantity = settings.ORDER_SIZE
        price = position

        order = self.exchange.place_order(price, quantity, order_type)
        sleep(settings.API_REST_INTERVAL)  # Don't hammer the API
        if settings.DRY_RUN is True or order['ordStatus'] != "Rejected":
            msg = [
                "\n   " + order_type.capitalize() + ":", str(quantity), order["symbol"],
                "@", str(price),
                "Gross Value: %.6f XBT" % XBt_to_XBT(cost(self.instrument, quantity, price)),
                "Margin Requirement: %.6f XBT" % XBt_to_XBT(margin(self.instrument, quantity, price))
            ]
            logger.info(" ".join(msg))
        else:
            logger.info("Order rejected: " + order['ordRejReason'])
            sleep(5)  # don't go crazy

        self.orders[index] = order

    def check_connection(self):
        """Ensure the WS connections are still open."""
        if not self.exchange.is_open():
            logger.error("Realtime data connection unexpectedly closed, exiting.")
            sys.exit()

    def check_orders(self):
        trade_data = self.exchange.get_trade_data()

        self.get_ticker()
        order_ids = [o["orderID"] for o in trade_data["orders"]]
        old_orders = self.orders.copy()
        print_status = False

        for index, order in old_orders.iteritems():
            # If an order fills, reset it
            if order["orderID"] not in order_ids:
                logger.info("Order filled, relisting: id: %s, price: %.2f, quantity: %d, side: %s" %
                            (order["orderID"], order["price"], order["orderQty"], order["side"]))
                del self.orders[index]
                self.place_order(index, order["side"])
                print_status = True
            # If an order drifts (reference price moves), cancel and replace it
            elif self.has_order_drifted(index, order):
                logger.info("Order drifted, refilling:, id: %s, price: %.2f, quantity: %d, side: %s" %
                            (order["orderID"], order["price"], order["orderQty"], order["side"]))
                self.exchange.cancel_order(order)
                self.place_order(index, order["side"])

        if print_status:
            marginBalance = trade_data["margin"]["marginBalance"]
            logger.info("Profit: %.6f XBT. Run Time: %s" %
                        (XBt_to_XBT(marginBalance - self.start_XBt), datetime.now() - self.start_time))

    # Given an order and its position in the stack, returns a boolean indicating if the reference
    # price has drifted too much and the order needs to be resubmitted.
    def has_order_drifted(self, index, order):
        reference = self.get_position(index)

        price_min = order['price'] * (1.00 - settings.RELIST_INTERVAL)
        price_max = order['price'] * (1.00 + settings.RELIST_INTERVAL)
        # Returns true if the order is outside its reference min or max
        return True if (reference > price_max or reference < price_min) else False

    def exit(self):
        logger.info("Shutting down. All open orders will be cancelled.")
        try:
            self.exchange.cancel_all_orders()
            self.exchange.bitmex.ws.exit()
        except errors.AuthenticationError as e:
            logger.info("Was not authenticated; could not cancel orders.")
        except Exception as e:
            logger.info("Unable to cancel orders: %s" % e)

    def run_loop(self):
        while True:
            for f, mtime in watched_files_mtimes:
                 if getmtime(f) > mtime:
                    logger.info("File change detected.")
                    self.restart()
            sleep(settings.LOOP_INTERVAL)
            self.check_orders()
            self.check_connection()
            sys.stdout.write("-----\n")
            sys.stdout.flush()

    def restart(self):
        logger.info("Restarting the market maker...")
        os.execv(sys.executable, [sys.executable] + sys.argv)

#
# Helpers
#


def XBt_to_XBT(XBt):
    return float(XBt) / constants.XBt_TO_XBT


def cost(instrument, quantity, price):
    mult = instrument["multiplier"]
    P = mult * price if mult >= 0 else mult / price
    return abs(quantity * P)


def margin(instrument, quantity, price):
    return cost(instrument, quantity, price) * instrument["initMargin"]


def run():
    logger.info('BitMEX Market Maker Version: %s\n' % constants.VERSION)

    om = OrderManager()
    # Try/except just keeps ctrl-c from printing an ugly stacktrace
    try:
        om.init()
        om.run_loop()
    except (KeyboardInterrupt, SystemExit):
        sys.exit()
