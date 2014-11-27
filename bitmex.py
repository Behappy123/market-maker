import urllib, urllib2, urlparse
from time import sleep
import json
import constants
import errors
import math
import time
import hashlib
import hmac
import base64

# https://www.bitmex.com/api/explorer/

class BitMEX(object):
    def __init__(self, base_url=None, symbol=None, login=None, password=None, otpToken=None, apiKey=None, apiSecret=None):
        self.base_url = base_url
        self.symbol = symbol
        self.token = None
        self.login = login
        self.password = password
        self.otpToken = otpToken
        self.apiKey = apiKey
        self.apiSecret = apiSecret

# Public methods
    def ticker_data(self):
        """Get ticker data"""
        data = self.get_instrument()

        ticker = {
            # Rounding to tickLog covers up float error
            "last": data['lastPrice'],
            "buy": data['bidPrice'],
            "sell": data['askPrice'],
            "mid": (float(data['bidPrice']) + float(data['askPrice'])) / 2
        }

        return {k: round(float(v), data['tickLog']) for k, v in ticker.iteritems()}

    def get_instrument(self):
        """Get an instrument's details"""
        api = "instrument"
        instruments = self._curl_bitmex(api=api, query={'filter': json.dumps({'symbol': self.symbol})})
        if len(instruments) == 0:
            print "Instrument not found: %s." % self.symbol
            exit(1)

        instrument = instruments[0]
        if instrument["state"] != "Open":
            print "The instrument %s is no longer open. State: %s" % (self.symbol, instrument["state"])
            exit(1)

        # tickLog is the log10 of tickSize
        instrument['tickLog'] = int(math.fabs(math.log10(instrument['tickSize'])))

        return instrument

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
    def authenticate(self):
        """Set BitMEX authentication information"""
        if self.apiKey:
            return
        loginResponse = self._curl_bitmex(
            api="user/login", 
            postdict={'email': self.login, 'password': self.password, 'token': self.otpToken})
        self.token = loginResponse['id']

    def authentication_required(function):
        def wrapped(self, *args, **kwargs):
            if not (self.token or self.apiKey):
                msg = "You must be authenticated to use this method"
                raise errors.AuthenticationError, msg
            else:
                return function(self, *args, **kwargs)
        return wrapped

    @authentication_required
    def funds(self):
        """Get your current balance."""
        userResponse = self._curl_bitmex(api="user")
        return userResponse['margin']

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

        endpoint = "order"
        postdict = {
            'symbol': self.symbol,
            'quantity': quantity,
            'price': price
        }
        print postdict
        return self._curl_bitmex(api=endpoint, postdict=postdict, verb="POST")

    @authentication_required
    def open_orders(self):
        """Get open orders."""

        api = "order"
        return self._curl_bitmex(
            api=api, 
            query={'filter': json.dumps({'ordStatus.isTerminated': False, 'symbol': self.symbol})},
            verb="GET"
        )

    @authentication_required
    def cancel(self, orderID):
        """Cancel an existing order.
           orderID: Order ID
        """

        api = "order"
        postdict = {
            'orderID': orderID,
        }
        return self._curl_bitmex(api=api, postdict=postdict, verb="DELETE")


    def _curl_bitmex(self, api, query=None, postdict=None, timeout=3, verb=None):
        url = self.base_url + api

        # Handle data
        if query:
            url = url + "?" + urllib.urlencode(query)
        if postdict:
            postdata = json.dumps(postdict)
            request = urllib2.Request(url, postdata)
        else:
            request = urllib2.Request(url)

        # Handle custom verbs
        if verb:
            request.get_method = lambda: verb
        else:
            verb = 'POST' if postdict else 'GET'

        # Headers
        request.add_header('user-agent', 'liquidbot-' + constants.VERSION)
        request.add_header('Content-Type', 'application/json')

        # If API Key is specified, calculate signature.
        # When using API Key authentication, you must supply nonce, public key, and signature.
        if self.apiKey:
            nonce = int(round(time.time() * 1000))
            request.add_header('api-nonce', nonce)
            request.add_header('api-key', self.apiKey)
            request.add_header('api-signature', self._generate_signature(verb, url, nonce, postdict))

        # Otherwise use accessToken (returned by login with email/password/otp)
        elif self.token:
            request.add_header('accessToken', self.token)

        # Make the request
        try:
            response = urllib2.urlopen(request, timeout=timeout)
        except urllib2.HTTPError, e:
            # 401 - Auth error. Re-auth and re-run this request.
            if e.code == 401:
                if self.token == None:
                    if postdict: print postdict
                    print "Login information or API Key incorrect, please check and restart."
                    print e.readline()
                    exit(1)
                print "Token expired, reauthenticating..."
                sleep(1)
                self.authenticate()
                return self._curl_bitmex(api, query, postdict, timeout, verb)
            # 503 - BitMEX temporary downtime, likely due to a deploy. Try again
            elif e.code == 503:
                print "Unable to contact the BitMEX API (503), retrying. " + \
                    "Request: %s \n %s" % (url, json.dumps(postdict))
                sleep(1)
                return self._curl_bitmex(api, query, postdict, timeout, verb)
            # Unknown Error
            else:
                print "Unhandled Error:", e
                print "Endpoint was: %s %s" % (verb, api)
                exit(1)
        except urllib2.URLError, e:
            print "Unable to contact the BitMEX API (URLError). Please check the URL. Retrying. " + \
                "Request: %s \n %s" % (url, json.dumps(postdict))
            sleep(1)
            return self._curl_bitmex(api, query, postdict, timeout, verb)

        return json.loads(response.read())

    # Generates an API signature.
    # A signature is HMAC_SHA256(secret, verb + path + nonce + data), base64 encoded.
    # Verb must be uppercased, url is relative, nonce must be an increasing 64-bit integer
    # and the data, if present, must be JSON without whitespace between keys.
    # 
    # For example, in psuedocode (and in real code below):
    # 
    # verb=POST
    # url=/api/v1/order
    # nonce=1416993995705
    # data={"symbol":"XBTZ14","quantity":1,"price":395.01}
    # signature = BASE64(HMAC_SHA256(secret, 'POST/api/v1/order1416993995705{"symbol":"XBTZ14","quantity":1,"price":395.01}'))
    def _generate_signature(self, verb, url, nonce, postdict):
        data = ''
        if postdict:
            # separators remove spaces from json
            # BitMEX expects signatures from JSON built without spaces
            data = json.dumps(postdict, separators=(',', ':'))
        parsedURL = urlparse.urlparse(url)
        path = parsedURL.path
        if parsedURL.query:
            path = path + '?' + parsedURL.query
        # print "Computing HMAC: %s" % verb + path + str(nonce) + data
        message = bytes(verb + path + str(nonce) + data).encode('utf-8')

        signature = base64.b64encode(hmac.new(self.apiSecret, message, digestmod=hashlib.sha256).digest())
        return signature

