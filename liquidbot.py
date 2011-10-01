import mtgox
from time import sleep
import sys
from urllib2 import URLError
from datetime import datetime

import settings


def timestamp_string():
    return "["+datetime.now().strftime("%I:%M:%S %p")+"]"

class ExchangeInterface:
    def __init__(self, dry_run=False):
        self.dry_run = dry_run
        self.mtgox = mtgox.MtGox()
        self.USD_DECIMAL_PLACES = 5

    def authenticate(self, login, password):
        if not self.dry_run:
            self.mtgox.authenticate(login, password)

    def cancel_all_orders(self):
        if self.dry_run:
            return

        trade_data = self.mtgox.open_orders(); sleep(1)
        orders = trade_data['orders']

        for order in orders:
            typestring = "sell" if order['type'] == 1 else "buy"
            print timestamp_string(), "Cancelling:", typestring, order['amount'], "@", order['price']
            while True:
                try:
                    self.mtgox.cancel(order['oid'], order['type']); sleep(1)
                except URLError as e:
                    print e.reason
                    sleep(10)
                except ValueError as e:
                    print e
                    sleep(10)
                else:
                    break

    def get_ticker(self):
        ticker = self.mtgox.ticker_data()["ticker"]

        return {"last": float(ticker["last"]), "buy": float(ticker["buy"]), "sell": float(ticker["sell"])}

    def get_trade_data(self):
        if self.dry_run:
            btc = float(settings.DRY_BTC)
            usd = float(settings.DRY_USD)
            orders = []
        else:
            while True:
                try:
                    trade_data = self.mtgox.open_orders(); sleep(1)
                except URLError as e:
                    print e.reason
                    sleep(10)
                except ValueError as e:
                    print e
                    sleep(10)
                else:
                    break

            btc = float(trade_data["btcs"])
            usd = float(trade_data["usds"])
            orders = []

            for o in trade_data["orders"]:
                order = {"id": o["oid"], "price": float(o["price"]), "amount": float(o["amount"])}
                order["type"] = "sell" if o["type"] == 1 else "buy"
                orders.append(order)

        return {"btc": btc, "usd": usd, "orders": orders}

    def place_order(self, price, amount, order_type):
        if settings.DRY_RUN:
            print timestamp_string(), order_type.capitalize() + ":", amount, "@", price
            return None

        if order_type == "buy":
            order_id = self.mtgox.buy(amount, price)["oid"]
        elif order_type == "sell":
            order_id = self.mtgox.sell(amount, price)["oid"]
        else:
            print "Invalid order type"
            exit()

        print timestamp_string(), order_type.capitalize() + ":", amount, "@", price, "id:", order_id

        return order_id

class OrderManager:
    def __init__(self):
        self.exchange = ExchangeInterface(settings.DRY_RUN)
        self.exchange.authenticate(settings.LOGIN, settings.PASSWORD)
        self.start_time = datetime.now()
        self.reset()

    def reset(self):
        self.exchange.cancel_all_orders()
        self.orders = {}

        ticker = self.exchange.get_ticker()
        self.start_position = ticker["last"]
        trade_data = self.exchange.get_trade_data()
        self.start_btc = trade_data["btc"]
        self.start_usd = trade_data["usd"]
        print timestamp_string(), "BTC:", self.start_btc, "  USD:", self.start_usd

        # Sanity check:
        if self.get_position(-1) >= ticker["sell"] or self.get_position(1) <= ticker["buy"]:
            print self.start_position
            print self.get_position(-1), ticker["sell"], self.get_position(1), ticker["buy"]
            print "Sanity check failed, exchange data is screwy"
            exit()

        for i in range(1, settings.ORDER_PAIRS + 1):
            self.place_order(-i, "buy")
            self.place_order(i, "sell")

        if settings.DRY_RUN:
            exit()

    def get_position(self, index):
        return round(self.start_position * (1+settings.INTERVAL)**index, self.exchange.USD_DECIMAL_PLACES)

    def place_order(self, index, order_type):
        position = self.get_position(index)
        order_id = self.exchange.place_order(position, settings.ORDER_SIZE, order_type)
        self.orders[index] = {"id": order_id, "type": order_type}

    def check_orders(self):
        trade_data = self.exchange.get_trade_data()
        order_ids = [o["id"] for o in trade_data["orders"]]
        old_orders = self.orders.copy()
        print_status = False

        for index, order in old_orders.iteritems():
            if order["id"] not in order_ids:
                print "Order filled, id:", order["id"]
                del self.orders[index]
                if order["type"] == "buy":
                    self.place_order(index + 1, "sell")
                else:
                    self.place_order(index - 1, "buy")
                print_status = True

        num_buys = 0
        num_sells = 0

        for order in self.orders.itervalues():
            if order["type"] == "buy":
                num_buys += 1
            else:
                num_sells += 1

        if num_buys < settings.ORDER_PAIRS:
            low_index = min(self.orders.keys())
            if num_buys == 0:
                # No buy orders left, so leave a gap
                low_index -= 1
            for i in range(1, settings.ORDER_PAIRS - num_buys + 1):
                self.place_order(low_index-i, "buy")

        if num_sells < settings.ORDER_PAIRS:
            high_index = max(self.orders.keys())
            if num_sells == 0:
                # No sell orders left, so leave a gap
                high_index += 1
            for i in range(1, settings.ORDER_PAIRS - num_sells + 1):
                self.place_order(high_index+i, "sell")

        if print_status:
            btc = trade_data["btc"]
            usd = trade_data["usd"]
            print "Profit:", btc - self.start_btc, "BTC,", usd - self.start_usd, "USD   Run Time:", datetime.now() - self.start_time


    def run_loop(self):
        while True:
            sleep(60)
            self.check_orders()
            sys.stdout.write(".")
            sys.stdout.flush()



om = OrderManager()
om.run_loop()
