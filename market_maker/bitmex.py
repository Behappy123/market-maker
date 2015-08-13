"""BitMEX API Connector."""
import requests
from time import sleep
import json
import constants
import errors
import uuid
import logging
from auth import AccessTokenAuth
from auth import APIKeyAuthWithExpires
from ws.ws_thread import BitMEXWebsocket


# https://www.bitmex.com/api/explorer/
class BitMEX(object):

    """BitMEX API Connector."""

    def __init__(self, base_url=None, symbol=None, login=None, password=None, otpToken=None,
                 apiKey=None, apiSecret=None, orderIDPrefix='mm_bitmex_'):
        """Init connector."""
        self.logger = logging.getLogger('root')
        self.base_url = base_url
        self.symbol = symbol
        self.token = None
        self.login = login
        self.password = password
        self.otpToken = otpToken
        self.apiKey = apiKey
        self.apiSecret = apiSecret
        if len(orderIDPrefix) > 13:
            raise ValueError("settings.ORDERID_PREFIX must be at most 13 characters long!")
        self.orderIDPrefix = orderIDPrefix

        # Prepare HTTPS session
        self.session = requests.Session()
        # These headers are always sent
        self.session.headers.update({'user-agent': 'liquidbot-' + constants.VERSION})

        # Create websocket for streaming data
        self.ws = BitMEXWebsocket(base_url, symbol)

    #
    # Public methods
    #
    def ticker_data(self):
        """Get ticker data."""
        return self.ws.get_ticker()

    def get_instrument(self):
        """Get an instrument's details."""
        instrument = self.ws.get_instrument()

        if instrument["state"] != "Open":
            self.logger.error("The instrument %s is no longer open. State: %s" % (self.symbol, instrument["state"]))
            exit(1)

        return instrument

    def market_depth(self):
        """Get market depth / orderbook."""
        return self.ws.market_depth()

    def recent_trades(self):
        """Get recent trades.

        Returns
        -------
        A list of dicts:
              {u'amount': 60,
               u'date': 1306775375,
               u'price': 8.7401099999999996,
               u'tid': u'93842'},

        """
        return self.ws.recent_trades()

    #
    # Authentication required methods
    #
    def authenticate(self):
        """Set BitMEX authentication information."""
        if self.apiKey:
            return
        loginResponse = self._curl_bitmex(
            api="user/login",
            postdict={'email': self.login, 'password': self.password, 'token': self.otpToken})
        self.token = loginResponse['id']
        self.session.headers.update({'access-token': self.token})

    def authentication_required(function):
        """Annotation for methods that require auth."""
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
        return self.ws.funds()

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
        # Generate a unique clOrdID with our prefix so we can identify it.
        clOrdID = self.orderIDPrefix + uuid.uuid4().bytes.encode('base64').rstrip('=\n')
        postdict = {
            'symbol': self.symbol,
            'quantity': quantity,
            'price': price,
            'clOrdID': clOrdID
        }
        return self._curl_bitmex(api=endpoint, postdict=postdict, verb="POST")

    @authentication_required
    def open_orders(self):
        """Get open orders."""
        return self.ws.open_orders(self.orderIDPrefix)

    @authentication_required
    def http_open_orders(self):
        """Get open orders via HTTP. Used on close to ensure we catch them all."""
        api = "order"
        orders = self._curl_bitmex(
            api=api,
            query={'filter': json.dumps({'ordStatus.isTerminated': False, 'symbol': self.symbol})},
            verb="GET"
        )
        # Only return orders that start with our clOrdID prefix.
        return [o for o in orders if str(o['clOrdID']).startswith(self.orderIDPrefix)]

    @authentication_required
    def cancel(self, orderID):
        """Cancel an existing order."""
        api = "order"
        postdict = {
            'orderID': orderID,
        }
        return self._curl_bitmex(api=api, postdict=postdict, verb="DELETE")

    def _curl_bitmex(self, api, query=None, postdict=None, timeout=3, verb=None):
        """Send a request to BitMEX Servers."""
        # Handle URL
        url = self.base_url + api

        # Default to POST if data is attached, GET otherwise
        if not verb:
            verb = 'POST' if postdict else 'GET'

        # Auth: Use Access Token by default, API Key/Secret if provided
        auth = AccessTokenAuth(self.token)
        if self.apiKey:
            auth = APIKeyAuthWithExpires(self.apiKey, self.apiSecret)

        # Make the request
        try:
            req = requests.Request(verb, url, data=postdict, auth=auth, params=query)
            prepped = self.session.prepare_request(req)
            response = self.session.send(prepped, timeout=timeout)
            # Make non-200s throw
            response.raise_for_status()

        except requests.exceptions.HTTPError, e:
            # 401 - Auth error. Re-auth and re-run this request.
            if response.status_code == 401:
                if self.token is None:
                    self.logger.error("Login information or API Key incorrect, please check and restart.")
                    self.logger.error("Error: " + response.text)
                    if postdict:
                        self.logger.error(postdict)
                    exit(1)
                self.logger.warning("Token expired, reauthenticating...")
                sleep(1)
                self.authenticate()
                return self._curl_bitmex(api, query, postdict, timeout, verb)

            # 404, can be thrown if order canceled does not exist.
            elif response.status_code == 404:
                if verb == 'DELETE':
                    self.logger.error("Order not found: %s" % postdict['orderID'])
                    return
                self.logger.error("Unable to contact the BitMEX API (404). " +
                                  "Request: %s \n %s" % (url, json.dumps(postdict)))
                exit(1)

            # 429, ratelimit
            elif response.status_code == 429:
                self.logger.error("Ratelimited on current request. Sleeping, then trying again. Try fewer " +
                                  "order pairs or contact support@bitmex.com to raise your limits. " +
                                  "Request: %s \n %s" % (url, json.dumps(postdict)))
                sleep(1)
                return self._curl_bitmex(api, query, postdict, timeout, verb)

            # 503 - BitMEX temporary downtime, likely due to a deploy. Try again
            elif response.status_code == 503:
                self.logger.warning("Unable to contact the BitMEX API (503), retrying. " +
                                    "Request: %s \n %s" % (url, json.dumps(postdict)))
                sleep(1)
                return self._curl_bitmex(api, query, postdict, timeout, verb)
            # Unknown Error
            else:
                self.logger.error("Unhandled Error: %s: %s %s" % (e, e.message, json.dumps(response.json(), indent=4)))
                self.logger.error("Endpoint was: %s %s" % (verb, api))
                exit(1)

        except requests.exceptions.Timeout, e:
            # Timeout, re-run this request
            self.logger.warning("Timed out, retrying...")
            return self._curl_bitmex(api, query, postdict, timeout, verb)

        except requests.exceptions.ConnectionError, e:
            self.logger.warning("Unable to contact the BitMEX API (ConnectionError). Please check the URL. Retrying. " +
                                "Request: %s \n %s" % (url, json.dumps(postdict)))
            sleep(1)
            return self._curl_bitmex(api, query, postdict, timeout, verb)

        return response.json()
