import websocket
import threading
from time import sleep
import settings
import json
import string
import logging

# Naive implementation of connecting to BitMEX websocket for streaming realtime data.
# The Marketmaker still interacts with this as if it were a REST Endpoint, but now it can get
# much more realtime data without polling the hell out of the API.
#
# The Websocket offers a bunch of data as raw properties right on the object.
# On connect, it synchronously asks for a push of all this data then returns.
# Right after, the MM can start using its data. It will be updated in realtime, so the MM can
# poll really often if it wants.
class BitMEXWebsocket():

    def __init__(self, endpoint="ws://localhost:3000/realtime", symbol="XBTN15"):
        self.logger = logging.getLogger()
        self.logger.debug("Initializing WebSocket.");
        self.reset(symbol)
        self.connect(endpoint, symbol)
        self.logger.info('Connected to WS.')
        # Connected. Push symbols
        self.getAccount()
        self.getSymbol(symbol)
        self.logger.info('Got all push data.')

        while self.ws.sock.connected:
            sleep(1)

    def connect(self, endpoint, symbol):
        # Subscribe to all pertinent endpoints
        subscriptions = [sub + ':' + symbol for sub in ["order", "execution", "instrument", "position"]]
        subscriptions += ["margin"]

        # We can pre-subscribe using the querystring
        wsURL = endpoint + "?subscribe=" + string.join(subscriptions, ",")
        self.ws = websocket.WebSocketApp(wsURL,
                                         on_message = self._on_message,
                                         on_close = self._on_close,
                                         # We can login using email/pass or API key
                                         # TODO implement API Key
                                         header = [
                                            "email: " + settings.LOGIN,
                                            "password: " + settings.PASSWORD
                                         ])
        self.wst = threading.Thread(target=self.ws.run_forever)
        self.wst.daemon = True
        self.wst.start()

        self.logger.debug("Starting thread")

        # Wait for connect before continuing
        conn_timeout = 5
        while not self.ws.sock or not self.ws.sock.connected and conn_timeout:
            sleep(1)
            conn_timeout -= 1

    def getAccount(self):
        self._send_command("getAccount")
        while not self.margin:
            sleep(0.1)

    def getSymbol(self, symbol):
        self._send_command("getSymbol", symbol);
        while not self.instrument:
            sleep(0.1)

    def _send_command(self, command, args=[]):
        self.ws.send(json.dumps({"op": command, "args": args}));

    def _on_message(self, ws, message):
        message = json.loads(message)
        self.logger.debug(json.dumps(message))
        if 'subscribe' in message:
            self.logger.debug("Subscribed to %s." % message['subscribe'])
        if 'action' in message and message['action'] == "partial":
            self.logger.debug("Got partial for %s" % message['table'])
            setattr(self, message['table'], message['data'])

    def _on_error(self, ws, error):
        self.logger.error("### Error : %s" % error)

    def _on_close(self, ws):
        self.logger.error('### Closed ###')

    def reset(self, symbol):
        self.symbol = symbol
        self.instrument = None
        self.orders = None
        self.margin = None
        self.position = None


if __name__ == "__main__" :
    # create console handler and set level to debug
    logger = logging.getLogger()
    logger.setLevel(logging.DEBUG)
    ch = logging.StreamHandler()
    # create formatter
    formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
    # add formatter to ch
    ch.setFormatter(formatter)
    logger.addHandler(ch)
    websocket.enableTrace(False)
    ws = BitMEXWebsocket()
