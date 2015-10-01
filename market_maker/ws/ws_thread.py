import sys
import websocket
import threading
import traceback
from time import sleep
import json
import string
import logging
import urlparse
import math
from market_maker import settings
from market_maker.auth.APIKeyAuth import generate_nonce, generate_signature


# Naive implementation of connecting to BitMEX websocket for streaming realtime data.
# The Marketmaker still interacts with this as if it were a REST Endpoint, but now it can get
# much more realtime data without polling the hell out of the API.
#
# The Websocket offers a bunch of data as raw properties right on the object.
# On connect, it synchronously asks for a push of all this data then returns.
# Right after, the MM can start using its data. It will be updated in realtime, so the MM can
# poll really often if it wants.
class BitMEXWebsocket():

    def __init__(self):
        self.logger = logging.getLogger('root')
        self.__reset()

    def connect(self, endpoint="", symbol="XBTN15", shouldAuth=True):
        '''Connect to the websocket and initialize data stores.'''

        self.logger.debug("Connecting WebSocket.")
        self.symbol = symbol
        self.shouldAuth = shouldAuth

        # We can subscribe right in the connection querystring, so let's build that.
        # Subscribe to all pertinent endpoints
        subscriptions = [sub + ':' + symbol for sub in ["instrument", "quote", "trade"]]
        if self.shouldAuth:
            subscriptions += [sub + ':' + symbol for sub in ["order", "execution", "position"]]
            subscriptions += ["margin"]

        # Get WS URL and connect.
        urlParts = list(urlparse.urlparse(endpoint))
        urlParts[0] = urlParts[0].replace('http', 'ws')
        urlParts[2] = "/realtime?subscribe=" + string.join(subscriptions, ",")
        wsURL = urlparse.urlunparse(urlParts)
        self.logger.info("Connecting to %s" % wsURL)
        self.__connect(wsURL)
        self.logger.info('Connected to WS. Fetching data images, this may take a moment...')

        # Connected. Push symbols
        self.__push_symbol(symbol)
        if self.shouldAuth:
            self.__push_account()
        self.logger.info('Got all market data. Starting.')

    #
    # Data methods
    #
    def get_instrument(self):
        # Turn the 'tickSize' into 'tickLog' for use in rounding
        instrument = self.data['instrument'][0]
        instrument['tickLog'] = int(math.fabs(math.log10(instrument['tickSize'])))
        return instrument

    def get_ticker(self):
        '''Return a ticker object. Generated from instrument.'''

        instrument = self.get_instrument()

        # If this is an index, we have to get the data from the last trade.
        if instrument['symbol'][0] == '.':
            ticker = {}
            ticker['mid'] = ticker['buy'] = ticker['sell'] = ticker['last'] = instrument['markPrice']
        # Normal instrument
        else:
            bid = instrument['bidPrice'] or instrument['lastPrice'] or 0
            ask = instrument['askPrice'] or instrument['lastPrice'] or 0
            ticker = {
                "last": instrument['lastPrice'],
                "buy": bid,
                "sell": ask,
                "mid": (bid + ask) / 2
            }

        # The instrument has a tickSize. Use it to round values.
        return {k: round(float(v or 0), instrument['tickLog']) for k, v in ticker.iteritems()}

    def funds(self):
        return self.data['margin'][0]

    def market_depth(self):
        return self.data['orderBook25']

    def open_orders(self, clOrdIDPrefix):
        orders = self.data['order']
        # Filter to only open orders (leavesQty > 0) and those that we actually placed
        return [o for o in orders if str(o['clOrdID']).startswith(clOrdIDPrefix) and o['leavesQty'] > 0]

    def position(self):
        positions = self.data['position']
        pos = [p for p in positions if p['symbol'] == self.symbol]
        return pos[0] if len(pos) else {'currentQty': 0}

    def recent_trades(self):
        return self.data['trade']

    #
    # Lifecycle methods
    #
    def error(self, err):
        self._error = err
        self.logger.error(err)
        self.exit()

    def exit(self):
        self.exited = True
        self.ws.close()

    #
    # Private methods
    #

    def __connect(self, wsURL):
        '''Connect to the websocket in a thread.'''
        self.logger.debug("Starting thread")

        self.ws = websocket.WebSocketApp(wsURL,
                                         on_message=self.__on_message,
                                         on_close=self.__on_close,
                                         on_open=self.__on_open,
                                         on_error=self.__on_error,
                                         # We can login using email/pass or API key
                                         header=self.__get_auth())

        self.wst = threading.Thread(target=lambda: self.ws.run_forever())
        self.wst.daemon = True
        self.wst.start()
        self.logger.info("Started thread")

        # Wait for connect before continuing
        conn_timeout = 5
        while (not self.ws.sock or not self.ws.sock.connected) and conn_timeout and not self._error:
            sleep(1)
            conn_timeout -= 1

        if not conn_timeout or self._error:
            self.logger.error("Couldn't connect to WS! Exiting.")
            self.exit()
            sys.exit(1)

    def __get_auth(self):
        '''Return auth headers. Will use API Keys if present in settings.'''

        if self.shouldAuth is False:
            return []

        if not settings.API_KEY:
            self.logger.info("Authenticating with email/password.")
            return [
                "email: " + settings.LOGIN,
                "password: " + settings.PASSWORD
            ]
        else:
            self.logger.info("Authenticating with API Key.")
            # To auth to the WS using an API key, we generate a signature of a nonce and
            # the WS API endpoint.
            nonce = generate_nonce()
            return [
                "api-nonce: " + str(nonce),
                "api-signature: " + generate_signature(settings.API_SECRET, 'GET', '/realtime', nonce, ''),
                "api-key:" + settings.API_KEY
            ]

    def __push_account(self):
        '''Ask the websocket for an account push. Gets margin, positions, and open orders'''
        self.__send_command("getAccount")
        # Wait for the keys to show up from the ws
        while not {'margin', 'position', 'order'} <= set(self.data):
            sleep(0.1)

    def __push_symbol(self, symbol):
        '''Ask the websocket for a symbol push. Gets instrument, orderBook, quote, and trade'''
        self.__send_command("getSymbol", symbol)
        while not {'instrument', 'trade', 'orderBook25', 'quote'} <= set(self.data):
            sleep(0.1)

    def __send_command(self, command, args=[]):
        '''Send a raw command.'''
        self.ws.send(json.dumps({"op": command, "args": args}))

    def __on_message(self, ws, message):
        '''Handler for parsing WS messages.'''
        message = json.loads(message)
        self.logger.debug(json.dumps(message))

        table = message['table'] if 'table' in message else None
        action = message['action'] if 'action' in message else None
        try:
            if 'subscribe' in message:
                if message['success']:
                    self.logger.debug("Subscribed to %s." % message['subscribe'])
                else:
                    self.error("Unable to subscribe to %s. Error: \"%s\" Please check and restart." %
                               (message['request']['args'][0], message['error']))
            elif 'status' in message and message['status'] == 401:
                self.error("Login information or API Key incorrect, please check and restart.")
            elif action:

                if table not in self.data:
                    self.data[table] = []

                if table not in self.keys:
                    self.keys[table] = []

                # There are four possible actions from the WS:
                # 'partial' - full table image
                # 'insert'  - new row
                # 'update'  - update row
                # 'delete'  - delete row
                if action == 'partial':
                    self.logger.debug("%s: partial" % table)
                    self.data[table] += message['data']
                    # Keys are communicated on partials to let you know how to uniquely identify
                    # an item. We use it for updates.
                    self.keys[table] = message['keys']
                elif action == 'insert':
                    self.logger.debug('%s: inserting %s' % (table, message['data']))
                    self.data[table] += message['data']
                elif action == 'update':
                    self.logger.debug('%s: updating %s' % (table, message['data']))
                    # Locate the item in the collection and update it.
                    for updateData in message['data']:
                        item = findItemByKeys(self.keys[table], self.data[table], updateData)
                        if not item:
                            return  # No item found to update. Could happen before push
                        item.update(updateData)
                        # Remove cancelled / filled orders
                        if table == 'order' and item['leavesQty'] <= 0:
                            self.data[table].remove(item)
                elif action == 'delete':
                    self.logger.debug('%s: deleting %s' % (table, message['data']))
                    # Locate the item in the collection and remove it.
                    for deleteData in message['data']:
                        item = findItemByKeys(self.keys[table], self.data[table], deleteData)
                        self.data[table].remove(item)
                else:
                    raise Exception("Unknown action: %s" % action)
        except:
            self.logger.error(traceback.format_exc())

    def __on_open(self, ws):
        self.logger.debug("Websocket Opened.")

    def __on_close(self, ws):
        self.logger.info('Websocket Closed')
        self.exit()

    def __on_error(self, ws, error):
        if not self.exited:
            self.error(error)

    def __reset(self):
        self.data = {}
        self.keys = {}
        self.exited = False
        self._error = None


def findItemByKeys(keys, table, matchData):
    for item in table:
        matched = True
        for key in keys:
            if item[key] != matchData[key]:
                matched = False
        if matched:
            return item

if __name__ == "__main__":
    # create console handler and set level to debug
    logger = logging.getLogger()
    logger.setLevel(logging.DEBUG)
    ch = logging.StreamHandler()
    # create formatter
    formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
    # add formatter to ch
    ch.setFormatter(formatter)
    logger.addHandler(ch)
    ws = BitMEXWebsocket("https://testnet.bitmex.com/api/v1")
    while(ws.ws.sock.connected):
        sleep(1)
