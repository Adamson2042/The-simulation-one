import requests
import time
from typing import Optional, Dict, List
import logging

logger = logging.getLogger(__name__)


class PolymarketClient:
    def __init__(self):
        self.gamma_api_base = "https://gamma-api.polymarket.com"
        self.clob_api_base = "https://clob.polymarket.com"
        self.session = requests.Session()
        self.session.headers.update(
            {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            }
        )
        
    def get_current_15min_epoch(self) -> int:
        now = int(time.time())
        return (now // 900) * 900


    def get_bitcoin_15min_slug(self) -> str:
        epoch = self.get_current_15min_epoch()
        return f"btc-updown-15m-{epoch}"


    def find_bitcoin_15min_event(self) -> Optional[Dict]:
        try:
            slug = self.get_bitcoin_15min_slug()
            print(f"Looking for event with slug: {slug}")

            url = f"{self.gamma_api_base}/events/slug/{slug}"

            logger.info("=" * 60)
            logger.info(f"Fetching BTC 15-min event using slug: {slug}")
            logger.info("=" * 60)

            response = self.session.get(url, timeout=10)
            response.raise_for_status()

            event = response.json()

            logger.info(f"Found event: {event.get('title')}")
            print(f"Event ID: {event.get('id')}")
            return event

        except Exception as e:
            logger.error(f"Error fetching Bitcoin 15-min event: {e}")
            return None

    def get_event_markets(self, event_id: str) -> List[Dict]:
        try:
            url = f"{self.gamma_api_base}/events/{event_id}"
            response = self.session.get(url, timeout=10)
            response.raise_for_status()
            event_data = response.json()
            return event_data.get("markets", [])
        except Exception as e:
            logger.error(f"Error fetching event markets: {e}")
            return []

    def get_market_tokens(self, condition_id: str) -> Optional[Dict]:
        try:
            url = f"{self.clob_api_base}/markets/{condition_id}"
            response = self.session.get(url, timeout=10)
            response.raise_for_status()
            market_data = response.json()
            tokens = market_data.get("tokens", [])

            up_token = None
            down_token = None

            for token in tokens:
                outcome = token.get("outcome", "").lower()

                if outcome in ["yes", "up"]:
                    up_token = token.get("token_id")

                if outcome in ["no", "down"]:
                    down_token = token.get("token_id")

            if up_token and down_token:
                return {
                    "up": up_token,
                    "down": down_token,
                    "market_data": market_data
                }

            logger.warning("Could not determine UP/DOWN tokens")

        except Exception as e: 
            logger.error(f"Error fetching market tokens: {e}")
            return None

    def get_order_book(self, token_id: str) -> Optional[Dict]:
        try:
            url = f"{self.clob_api_base}/book"
            params = {"token_id": token_id}
            response = self.session.get(url, params=params, timeout=10)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Error fetching order book: {e}")
            return None

    def get_best_prices(self, token_id: str) -> Dict[str, Optional[float]]:
        order_book = self.get_order_book(token_id)
        if not order_book:
            return {"bid": None, "ask": None}

        bids = order_book.get("bids", [])
        asks = order_book.get("asks", [])

        best_bid = float(bids[0]["price"]) if bids else None
        best_ask = float(asks[0]["price"]) if asks else None

        return {"bid": best_bid, "ask": best_ask}

    def detect_market(self) -> Optional[Dict]:
        event = self.find_bitcoin_15min_event()
        if not event:
            logger.info("No Bitcoin 15-min event found")
            return None

        event_id = event.get("id")
        markets = self.get_event_markets(event_id)

        if not markets:
            logger.warning(f"No markets found for event {event_id}")
            return None

        market = markets[0]
        market_id = market.get("conditionId")

        token_data = self.get_market_tokens(market_id)
        if not token_data:
            logger.warning(f"Could not fetch tokens for market {market_id}")
            return None

        return {
            "event_id": event_id,
            "event_title": event.get("title"),
            "market_id": market_id,
            "token_id_up": token_data["up"],
            "token_id_down": token_data["down"],
        }
