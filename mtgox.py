import urllib, urllib2
import json

# https://mtgox.com/support/tradeAPI

class MtGox(object):
    def __init__(self, username=None, password=None):
        self.username = username
        self.password = password

# Public methods
    def ticker_data(self):
        """Get ticker data"""
        api = "data/ticker.php"
        return self._curl_mtgox(api=api)

    def market_depth(self):
        """Get market depth"""
        api = "data/getDepth.php"
        return self._curl_mtgox(api=api)

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

        api = "data/getTrades.php"
        return self._curl_mtgox(api=api)

    @property
    def snapshot(self):
        """Get current BBO
        """
        order_book = self.market_depth()
        return dict(
            bid=order_book['bids'][0][0],
            ask=order_book['asks'][0][0],
            size_bid=order_book['bids'][0][1],
            size_ask=order_book['asks'][0][1],
            )

# Authentication required methods
    def authenticate(self, username, password):
        """Set MtGox authentication information"""
        self.username = username
        self.password = password

    def authentication_required(function):
        def wrapped(self, *args, **kwargs):
            if not (self.username and self.password):
                msg = "You must be authenticated to use this method"
                raise Exception, msg
            else:
                return function(self, *args, **kwargs)
        return wrapped

    @authentication_required
    def funds(self):
        """Get your current balance."""
        api = "getFunds.php"
        postdict = {
            'name':self.username,
            'pass':self.password,
            }
        return self._curl_mtgox(api=api, postdict=postdict)

    @authentication_required
    def buy(self, amount, price):
        """Place a buy order.

           Returns list of your open orders

        """

        api = "buyBTC.php"
        postdict = {
            'name':   self.username,
            'pass':   self.password,
            'amount': amount,
            'price':  price,
            }
        return self._curl_mtgox(api=api, postdict=postdict)

    @authentication_required
    def sell(self, amount, price):
        """Place a sell order.

           Returns list of your open orders

        """

        api = "sellBTC.php"
        postdict = {
            'name':   self.username,
            'pass':   self.password,
            'amount': amount,
            'price':  price,
            }
        return self._curl_mtgox(api=api, postdict=postdict)

    @authentication_required
    def open_orders(self):
        """Get open orders.

           In response, these keys:
               oid:    Order ID
               type:   1 for sell order or 2 for buy order
               status: 1 for active, 2 for not enough funds

        """

        api = "getOrders.php"
        postdict = {
            'name':   self.username,
            'pass':   self.password,
            }
        return self._curl_mtgox(api=api, postdict=postdict)

    @authentication_required
    def cancel(self, oid, order_type):
        """Cancel an existing order.

           oid: Order ID
           type: 1 for sell order or 2 for buy order

        """

        api = "cancelOrder.php"
        postdict = {
            'name':   self.username,
            'pass':   self.password,
            'oid':    oid,
            'type':   order_type,
            }
        return self._curl_mtgox(api=api, postdict=postdict)

    @authentication_required
    def send(self, btca, amount, group1="BTC"):
        """Send BTC to someone.

           btca:     bitcoin address to send to
           amount:   amount

           Not really sure what this does or what the 'group1' arg is for,
           just copying from the API.

           https://mtgox.com/code/withdraw.php?name=blah&pass=blah&group1=BTC&btca=bitcoin_address_to_send_to&amount=#

        """

        # In [3]: m.send(btca="17kXoRWgeTRAyVhyJoMeZz5xHz98xPoiA", amount=1.98)
        # Out[3]: {u'error': u'Not available yet'}


        api = "withdraw.php"
        postdict = {
            'name':   self.username,
            'pass':   self.password,
            'btca':   btca,
            'amount': amount,
            }
        return self._curl_mtgox(api=api, postdict=postdict)

    def _curl_mtgox(self, api, postdict=None, timeout=8):
        BASE_URL = "https://mtgox.com/code/"
        url = BASE_URL + api
        if postdict:
            postdata = urllib.urlencode(postdict)
            request = urllib2.Request(url, postdata)
        else:
            request = urllib2.Request(url)
        response = urllib2.urlopen(request, timeout=timeout)
        return json.loads(response.read())

