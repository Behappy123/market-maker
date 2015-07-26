from os.path import join
import logging

# Available levels: logging.(DEBUG|INFO|WARN|ERROR)
LOG_LEVEL = logging.INFO

# API URL.
BASE_URL = "https://www.bitmex.com/api/v1/"

# Credentials
LOGIN = "test@test.com"
PASSWORD = "password"
OTPTOKEN = "" # OTP token, if enabled (Google Authenticator)

# If using permanent API keys, leave the above as blank strings and fill these out.
API_KEY = ""
API_SECRET = ""

# Instrument to market make.
SYMBOL = "XBTP14"

# If true, don't set up any orders, just say what we would do
#DRY_RUN = True
DRY_RUN = False

# How often to re-check the orderbook and replace orders
LOOP_INTERVAL = 60

# Wait times between orders / errors
API_REST_INTERVAL = 1
API_ERROR_INTERVAL = 10

# If we're doing a dry run, use these numbers for BTC balances
DRY_BTC = 50

# How many pairs of buy/sell orders to keep open
ORDER_PAIRS = 6

# How many contracts each order should contain
ORDER_SIZE = 500

# Distance between successive orders, as a percentage (example: 0.005 for 0.5%)
INTERVAL = 0.005

# Minimum spread to maintain, in percent, between asks & bids
MIN_SPREAD = 0.01

# If True, market-maker will place orders just inside the existing spread and work the interval % outwards,
# rather than starting in the middle and killing potentially profitable spreads.
MAINTAIN_SPREADS = True

# Each order is designed to be (INTERVAL*n)% away from the spread.
# If the spread changes and the order has moved outside its bound defined as
# (INTERVAL*n) - RELIST_INTERVAL < current_spread < (INTERVAL*n) + RELIST+INTERVAL
# it will be resubmitted.
# 0.01 = 1%
RELIST_INTERVAL = 0.01

# To uniquely identify orders placed by this bot, the bot sends a ClOrdID (Client order ID) that is attached
# to each order so its source can be identified. This keeps the market maker from cancelling orders that are
# manually placed, or orders placed by another bot.
#
# If you are running multiple bots on the same symbol, give them unique ORDERID_PREFIXes - otherwise they will
# cancel each others' orders.
# Max length is 13 characters.
ORDERID_PREFIX = "mm_bitmex_"

# If any of these files (and this file) changes, reload the bot.
WATCHED_FILES = [join("market_maker", f) for f in ["market_maker.py", "bitmex.py", __file__]]
