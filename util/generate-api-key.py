import urllib
import urllib2
from time import sleep
import json
from market_maker import constants
from market_maker import errors
import math
import ssl
import getpass
import pprint
import signal

# Edit this to True if you'd like to create a Testnet key.
USE_TESTNET = False

BITMEX_TESTNET = "https://testnet.bitmex.com"
BITMEX_PRODUCTION = "https://www.bitmex.com"


def main():
    print("########################")
    print("BitMEX API Key Interface")
    print("########################\n")

    apiObj = auth()
    while True:
        prompt(apiObj)


def prompt(apiObj):
    operations = ['list_keys', 'create_key', 'enable_key', 'disable_key', 'delete_key']
    print("Available operations: " + ', '.join(operations))
    operation = raw_input("Enter command: ")
    if operation not in operations:
        print("ERROR: Operation not supported: %s" % operation)
        exit(1)

    getattr(apiObj, operation)()
    print("\nOperation completed. Press <ctrl+c> to quit.")


def auth():
    print("Please log in.")
    email = raw_input("Email: ")
    password = getpass.getpass("Password: ")
    otpToken = raw_input("OTP Token (if enabled. If not, press <enter>): ")
    apiObj = BitMEX(email, password, otpToken)
    print("\nSuccessfully logged in.")
    return apiObj


class BitMEX(object):
    def __init__(self, email=None, password=None, otpToken=None):
        self.base_url = (BITMEX_TESTNET if USE_TESTNET else BITMEX_PRODUCTION) + "/api/v1"
        self.accessToken = None
        self.accessToken = self._curl_bitmex("/user/login",
                                             postdict={"email": email, "password": password, "token": otpToken})["id"]

    def create_key(self):
        """Create an API key."""
        print("Creating key. Please input the following options:")
        name = raw_input("Key name (optional): ")
        print("To make this key more secure, you should restrict the IP addresses that can use it. ")
        print("To use with all IPs, leave blank or use 0.0.0.0/0.")
        print("To use with a single IP, append '/32', such as 207.39.29.22/32. ")
        print("See this reference on CIDR blocks: http://software77.net/cidr-101.html")
        cidr = raw_input("CIDR (optional): ")
        key = self._curl_bitmex("/apiKey",
                                postdict={"name": name, "cidr": cidr, "enabled": True})

        print("Key created. Details:\n")
        print("API Key:    " + key["id"])
        print("Secret:     " + key["secret"])
        print("\nSafeguard your secret key! If somebody gets a hold of your API key and secret,")
        print("your account can be taken over completely.")
        print("\nKey generation complete.")

    def list_keys(self):
        """List your API Keys."""
        keys = self._curl_bitmex("/apiKey/")
        print(json.dumps(keys, sort_keys=True, indent=4))

    def enable_key(self):
        """Enable an existing API Key."""
        print("This command will enable a disabled key.")
        apiKeyID = raw_input("API Key ID: ")
        try:
            key = self._curl_bitmex("/apiKey/enable",
                                    postdict={"apiKeyID": apiKeyID})
            print("Key with ID %s enabled." % key["id"])
        except:
            print("Unable to enable key, please try again.")
            self.enable_key()

    def disable_key(self):
        """Disable an existing API Key."""
        print("This command will disable a enabled key.")
        apiKeyID = raw_input("API Key ID: ")
        try:
            key = self._curl_bitmex("/apiKey/disable",
                                    postdict={"apiKeyID": apiKeyID})
            print("Key with ID %s disabled." % key["id"])
        except:
            print("Unable to disable key, please try again.")
            self.disable_key()

    def delete_key(self):
        """Delete an existing API Key."""
        print("This command will delete an API key.")
        apiKeyID = raw_input("API Key ID: ")
        try:
            self._curl_bitmex("/apiKey/",
                              postdict={"apiKeyID": apiKeyID}, verb='DELETE')
            print("Key with ID %s disabled." % apiKeyID)
        except:
            print("Unable to delete key, please try again.")
            self.delete_key()

    def _curl_bitmex(self, api, query=None, postdict=None, timeout=3, verb=None):
        url = self.base_url + api
        if query:
            url = url + "?" + urllib.urlencode(query)
        if postdict:
            postdata = urllib.urlencode(postdict)
            request = urllib2.Request(url, postdata)
        else:
            request = urllib2.Request(url)

        if verb:
            request.get_method = lambda: verb

        request.add_header('user-agent', 'BitMEX-generate-api-key')
        if self.accessToken:
            request.add_header('accessToken', self.accessToken)

        try:
            response = urllib2.urlopen(request, timeout=timeout)
        except urllib2.HTTPError, e:
            if e.code == 401:
                print("Login information incorrect, please check and restart.")
                exit(1)
            # 503 - BitMEX temporary downtime, likely due to a deploy. Try again
            elif e.code == 503:
                print("Unable to contact the BitMEX API (503). Please try again later." +
                      "Request: %s \n %s" % (url, json.dumps(postdict)))
                exit(1)
            else:
                print("Error:", e)
                print("Endpoint was: " + api)
                print("Please try again.")
                raise e
        except (urllib2.URLError, ssl.SSLError), e:
            print("Unable to contact the BitMEX API (URLError). Please check the URL. Please try again later. " +
                  "Request: %s \n %s" % (url, json.dumps(postdict)))
            exit(1)

        return json.loads(response.read())


def signal_handler(signal, frame):
    print('\nExiting...')
    exit(0)

signal.signal(signal.SIGINT, signal_handler)

main()
