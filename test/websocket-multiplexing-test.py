from websocket import create_connection
import json, base64, hashlib, urlparse, hmac, time, uuid

###
# websocket-apikey-auth-test.py
#
# Reference Python implementation for multiplexing realtime data for multiple
# users through a single websocket connection.
###

# Replace these with your keys.
KEYS = {
    "CfwQ4SZ6gM_t6dIy1bCLJylX": "f9XOPLacPCZJ1dvPzN8B6Et7nMEaPGeomMSHk8Cr2zD4NfCY"
}

# Switch these comments to use testnet instead.
BITMEX_URL = "ws://localhost:3000"
# BITMEX_URL="wss://testnet.bitmex.com"
# BITMEX_URL="wss://www.bitmex.com"

VERB = "GET"
AUTH_ENDPOINT = "/realtime"  # for the purpose of the API Key check, we're still using /realtime
ENDPOINT = "/realtimemd?transport=websocket&b64=1"


def main():
    """Authenticate with the BitMEX API & request account information."""
    test_with_message()


def test_with_message():
    # Initial connection - BitMEX sends a welcome message.
    print("Connecting to " + BITMEX_URL + ENDPOINT)
    ws = create_connection(BITMEX_URL + ENDPOINT)
    print("Receiving Welcome Message...")
    result = ws.recv()
    print("Received '%s'" % result)
    connID = json.loads(result[1:])['sid']

    # Open multiplexed connections.
    for key, secret in KEYS.iteritems():
        # This is up to you, most use microtime but you may have your own scheme so long as it's increasing
        # and doesn't repeat.
        nonce = int(round(time.time() * 1000))
        # See signature generation reference at https://www.bitmex.com/app/apiKeys
        signature = bitmex_signature(secret, VERB, AUTH_ENDPOINT, nonce)

        # Open a new multiplexed connection.
        # See https://github.com/cayasso/primus-multiplex for more details
        # Format is "type", "id", "topic", "payload"
        # Types are 0 - Message, 1 - Subscribe, 2 - Unsubscribe
        # connID = id()
        channelName = "userAuth:" + key + ":" + str(nonce) + ":" + signature
        request = [1, connID, channelName]
        print(json.dumps(request))
        ws.send(json.dumps(request))
        print("Sent Auth request")
        result = ws.recv()
        print("Received '%s'" % result)

        # Send a request that requires authorization on this multiplexed connection.
        op = {"op":"subscribe", "args":"position"}
        request = [0, connID, channelName, op]
        ws.send(json.dumps(request))
        print("Sent subscribe")
        result = ws.recv()
        print("Received '%s'" % result)
        result = ws.recv()
        print("Received '%s'" % result)

    ws.close()


# Generates a random ID.
def id():
    return uuid.uuid4().bytes.encode('base64').rstrip('=\n')


# Generates an API signature.
# A signature is HMAC_SHA256(secret, verb + path + nonce + data), base64 encoded.
# Verb must be uppercased, url is relative, nonce must be an increasing 64-bit integer
# and the data, if present, must be JSON without whitespace between keys.
def bitmex_signature(apiSecret, verb, url, nonce, postdict=None):
    """Given an API Secret and data, create a BitMEX-compatible signature."""
    data = ''
    if postdict:
        # separators remove spaces from json
        # BitMEX expects signatures from JSON built without spaces
        data = json.dumps(postdict, separators=(',', ':'))
    parsedURL = urlparse.urlparse(url)
    path = parsedURL.path
    if parsedURL.query:
        path = path + '?' + parsedURL.query
    # print("Computing HMAC: %s" % verb + path + str(nonce) + data)
    message = bytes(verb + path + str(nonce) + data).encode('utf-8')

    signature = hmac.new(apiSecret, message, digestmod=hashlib.sha256).hexdigest()
    return signature

if __name__ == "__main__":
    main()
