from websocket import create_connection
import json, base64, hashlib, urlparse, hmac, time

###
# websocket-apikey-auth-test.py
#
# Reference Python implementation for authorizing with websocket.
# See https://www.bitmex.com/app/wsAPI for more details, including a list
# of methods.
###

# These are not real keys - replace them with your keys.
API_KEY = "CfwQ4SZ6gM_t6dIy1bCLJylX"
API_SECRET = "f9XOPLacPCZJ1dvPzN8B6Et7nMEaPGeomMSHk8Cr2zD4NfCY"

# Switch these comments to use testnet instead.
# BITMEX_URL = "wss://testnet.bitmex.com"
BITMEX_URL = "wss://www.bitmex.com"

VERB = "GET"
ENDPOINT = "/realtime"


def main():
    """Authenticate with the BitMEX API & request account information."""
    test_with_message()
    test_with_querystring()


def test_with_message():
    # This is up to you, most use microtime but you may have your own scheme so long as it's increasing
    # and doesn't repeat.
    nonce = int(round(time.time() * 1000))
    # See signature generation reference at https://www.bitmex.com/app/apiKeys
    signature = bitmex_signature(API_SECRET, VERB, ENDPOINT, nonce)

    # Initial connection - BitMEX sends a welcome message.
    ws = create_connection(BITMEX_URL + ENDPOINT)
    print("Receiving Welcome Message...")
    result = ws.recv()
    print("Received '%s'" % result)

    # Send API Key with signed message.
    request = {"op": "authKey", "args": [API_KEY, nonce, signature]}
    ws.send(json.dumps(request))
    print("Sent Auth request")
    result = ws.recv()
    print("Received '%s'" % result)

    # Send a request that requires authorization.
    request = {"op": "subscribe", "args": "position"}
    ws.send(json.dumps(request))
    print("Sent subscribe")
    result = ws.recv()
    print("Received '%s'" % result)
    result = ws.recv()
    print("Received '%s'" % result)

    ws.close()


def test_with_querystring():
    # This is up to you, most use microtime but you may have your own scheme so long as it's increasing
    # and doesn't repeat.
    nonce = int(round(time.time() * 1000))
    # See signature generation reference at https://www.bitmex.com/app/apiKeys
    signature = bitmex_signature(API_SECRET, VERB, ENDPOINT, nonce)

    # Initial connection - BitMEX sends a welcome message.
    ws = create_connection(BITMEX_URL + ENDPOINT +
                           "?api-nonce=%s&api-signature=%s&api-key=%s" % (nonce, signature, API_KEY))
    print("Receiving Welcome Message...")
    result = ws.recv()
    print("Received '%s'" % result)

    # Send a request that requires authorization.
    request = {"op": "subscribe", "args": "position"}
    ws.send(json.dumps(request))
    print("Sent subscribe")
    result = ws.recv()
    print("Received '%s'" % result)
    result = ws.recv()
    print("Received '%s'" % result)

    ws.close()


# Generates an API signature.
# A signature is HMAC_SHA256(secret, verb + path + nonce + data), hex encoded.
# Verb must be uppercased, url is relative, nonce must be an increasing 64-bit integer
# and the data, if present, must be JSON without whitespace between keys.
def bitmex_signature(apiSecret, verb, url, nonce, postdict=None):
    """Given an API Secret key and data, create a BitMEX-compatible signature."""
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
