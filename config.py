import os
from dotenv import load_dotenv
from decimal import Decimal

load_dotenv()

GAMMA_API_BASE = "https://gamma-api.polymarket.com"
CLOB_API_BASE = "https://clob.polymarket.com"

GAMMA_EVENTS_ENDPOINT = f"{GAMMA_API_BASE}/events"
GAMMA_MARKETS_ENDPOINT = f"{GAMMA_API_BASE}/markets"
CLOB_ORDERBOOK_ENDPOINT = f"{CLOB_API_BASE}/book"
CLOB_MARKETS_ENDPOINT = f"{CLOB_API_BASE}/markets"

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_ANON_KEY")

INITIAL_BALANCE = Decimal("1000")
MAX_DAILY_TRADES = 100

BUY_LIMIT_PRICE = Decimal("0.05")
SELL_LIMIT_PRICE = Decimal("0.15")
STAKE_SIZE = Decimal("10")

MARKET_DETECTION_RETRY_DELAY = 10
TRADED_MARKET_RETRY_DELAY = 30

BITCOIN_KEYWORDS = ["bitcoin", "btc"]
FIVE_MIN_KEYWORDS = ["5 minute", "5-minute", "5min"]

LOG_LEVEL = "INFO"
LOG_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"

API_REQUEST_TIMEOUT = 30
API_RATE_LIMIT_DELAY = 1
