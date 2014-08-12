import urllib, urllib2
import json
import constants

# https://www.bitmex.com/api/explorer/

class BitMEX(object):
    def __init__(self, base_url=None, symbol=None):
        self.base_url = base_url
        self.symbol = symbol
        self.token = None

# Public methods
    def ticker_data(self):
        """Get ticker data"""
        data = self.get_instrument()
        return {
            "last": data['lastPrice'],
            "buy": data['bidPrice'],
            "sell": data['askPrice']
        }

    def get_instrument(self):
        """Get an instrument's details"""
        api = "instrument"
        return self._curl_bitmex(api=api, query={'filter': json.dumps({'symbol': self.symbol})})[0]

    def market_depth(self):
        """Get market depth / orderbook"""
        api = "orderBook"
        return self._curl_bitmex(api=api, query={'symbol': self.symbol})

    def recent_trades(self):
        """Get recent trades

           Returns
           -------
           A list of dicts:
                 {u'amount': 60,
                  u'date': 1306775375,
                  u'price': 8.7401099999999996,
                  u'tid': u'93842'},

        """

        api = "trade/getRecent"
        return self._curl_bitmex(api=api)

    @property
    def snapshot(self):
        """Get current BBO"""
        order_book = self.market_depth()
        return {
            'bid': order_book[0]['bidPrice'],
            'ask': order_book[0]['askPrice'],
            'size_bid': order_book[0]['bidSize'],
            'size_ask': order_book[0]['askSize']
        }

# Authentication required methods
    def authenticate(self, email, password):
        """Set BitMEX authentication information"""
        loginResponse = self._curl_bitmex(api="user/login", postdict={'email': email, 'password': password})
        self.token = loginResponse['id']

    def authentication_required(function):
        def wrapped(self, *args, **kwargs):
            if not (self.token):
                msg = "You must be authenticated to use this method"
                raise Exception, msg
            else:
                return function(self, *args, **kwargs)
        return wrapped

    @authentication_required
    def funds(self):
        """Get your current balance."""
        userResponse = self._curl_bitmex(api="user")
        return userResponse['margin']['marginBalance'] / float(constants.XBt_TO_XBT) # XBT, not XBt

    @authentication_required
    def buy(self, quantity, price):
        """Place a buy order.

        Returns order object. ID: orderID

        """

        return self.place_order(quantity, price)

    @authentication_required
    def sell(self, quantity, price):
        """Place a sell order.

        Returns order object. ID: orderID

        """

        return self.place_order(-quantity, price)

    @authentication_required
    def place_order(self, quantity, price):
        """Place an order."""

        if price < 0:
            raise Exception("Price must be positive.")

        endpoint = "order/new"
        postdict = {
            'symbol': self.symbol,
            'quantity': quantity,
            'price': price
        }
        print postdict
        return self._curl_bitmex(api=endpoint, postdict=postdict)

    @authentication_required
    def open_orders(self):
        """Get open orders."""

        api = "order/myOpenOrders"
        return self._curl_bitmex(api=api)

    @authentication_required
    def cancel(self, orderID):
        """Cancel an existing order.
           orderID: Order ID
        """

        api = "order/cancel"
        postdict = {
            'orderID': orderID,
        }
        return self._curl_bitmex(api=api, postdict=postdict)


    def _curl_bitmex(self, api, query=None, postdict=None, timeout=8):
        url = self.base_url + api
        if query:
            url = url + "?" + urllib.urlencode(query)
        if postdict:
            postdata = urllib.urlencode(postdict)
            request = urllib2.Request(url, postdata)
        else:
            request = urllib2.Request(url)

        request.add_header('user-agent', 'liquidbot-' + constants.VERSION)
        if self.token:
            request.add_header('accessToken', self.token)

        response = urllib2.urlopen(request, timeout=timeout)
        return json.loads(response.read())

