import asyncio
import logging
from typing import Optional, Dict, Any
from datetime import datetime
import time
import aiohttp
from supabase import create_client, Client

import config

logger = logging.getLogger(__name__)


class MarketDetector:
    def __init__(self, supabase_client: Client):
        self.supabase = supabase_client
        self.session: Optional[aiohttp.ClientSession] = None

    async def initialize(self):
        self.session = aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=config.API_REQUEST_TIMEOUT))

    async def close(self):
        if self.session:
            await self.session.close()

    def get_current_5min_epoch(self) -> int:
        now = int(time.time())
        return (now // 300) * 300


    def get_bitcoin_5min_slug(self) -> str:
        epoch = self.get_current_5min_epoch()
        return f"btc-updown-5m-{epoch}"

    async def _make_request(self, url: str, params: Optional[Dict[str, Any]] = None) -> Optional[Dict]:
        try:
            async with self.session.get(url, params=params) as response:
                if response.status == 200:
                    return await response.json()
                else:
                    logger.error(f"API request failed with status {response.status}: {url}")
                    return None
        except Exception as e:
            logger.error(f"Error making request to {url}: {e}")
            return None
        
    async def find_bitcoin_5min_event(self) -> Optional[Dict]:
        try:
            slug = self.get_bitcoin_5min_slug()
            logger.info(f"Fetching BTC 5-min event with slug: {slug}")

            url = f"{config.GAMMA_EVENTS_ENDPOINT}/slug/{slug}"
            event = await self._make_request(url)
            logger.info(f"Found event: {event.get('title')}")
            return event

        except Exception as e:
            logger.error(f"Error fetching BTC 5-min event: {e}")
            return None

    async def detect_current_event(self) -> Optional[Dict[str, Any]]:
        logger.info("Detecting current BTC 5-minute event...")

        event = await self.find_bitcoin_5min_event()
        if not event:
            return None

        event_id = event.get("id")
        logger.info(f"Event ID: {event_id}")

        existing = (
            self.supabase
            .table("events")
            .select("event_id, traded")
            .eq("event_id", event_id)
            .execute()
        )

        logger.info(f"Existing: {existing}")

        if existing.data and existing.data[0].get("traded"):
            logger.info(f"Event {event_id} already traded, skipping...")
            return None
        
        event_data = {
            "event_id": event_id,
            "title": event.get("title"),
            "start_time": event.get("startDate"),
            "end_time": event.get("endDate"),
            "status": "active",
            "traded": False
        }

        response = (
            self.supabase
            .table("events")
            .upsert(event_data, on_conflict="event_id")
            .execute()
        )

        if hasattr(response, "error") and response.error:
            logger.error(f"Failed to upsert event {event_id}: {response.error}")
            return None

        logger.info(f"✅ Detected BTC 5-min event: {event.get('title')} (ID: {event_id})")
        return event

        """ params = {
            "active": "true",
            "closed": "false",
            "limit": 50
        } """

        """ events_data = await self._make_request(config.GAMMA_EVENTS_ENDPOINT, params) """

        """ if not events_data:
            logger.warning("No events data received from Gamma API")
            return None """

        """ events = events_data if isinstance(events_data, list) else events_data.get("data", [])

        for event in events:
            if self._is_btc_5min_event(event):
                event_id = event.get("id")

                existing = self.supabase.table("events").select("*").eq("event_id", event_id).execute()

                if existing.data and existing.data[0].get("traded"):
                    logger.info(f"Event {event_id} already traded, skipping...")
                    continue

                event_data = {
                    "event_id": event_id,
                    "title": event.get("title"),
                    "start_time": event.get("startDate"),
                    "end_time": event.get("endDate"),
                    "status": "active",
                    "traded": False
                }

                self.supabase.table("events").upsert(event_data, on_conflict="event_id").execute()

                logger.info(f"Detected BTC 5-min event: {event.get('title')} (ID: {event_id})")
                return event 

        logger.info("No untradable BTC 5-minute events found")
        return None"""

    async def detect_current_market(self, event_id: str) -> Optional[Dict[str, Any]]:
        logger.info(f"Detecting market for event {event_id}...")

        params = {
            "event_id": event_id,
            "active": "true",
            "closed": "false"
        }

        markets_data = await self._make_request(config.GAMMA_MARKETS_ENDPOINT, params)

        if not markets_data:
            logger.warning(f"No markets data received for event {event_id}")
            return None

        markets = markets_data if isinstance(markets_data, list) else markets_data.get("data", [])

        if not markets:
            logger.warning(f"No active markets found for event {event_id}")
            return None

        market = markets[0]
        market_id = market.get("conditionId")

        market_data = {
            "event_id": event_id,
            "market_id": market_id,
            "question": market.get("question", ""),
            "status": "active"
        }

        self.supabase.table("markets").upsert(market_data, on_conflict="market_id").execute()

        logger.info(f"Detected market: {market.get('question')} (ID: {market_id})")
        return market

    async def fetch_token_ids(self, market_id: str) -> Optional[Dict[str, str]]:
        logger.info(f"Fetching token IDs for market {market_id}...")

        url = f"{config.CLOB_MARKETS_ENDPOINT}/{market_id}"
        market_info = await self._make_request(url)

        if not market_info:
            logger.warning(f"No market info received for market {market_id}")
            return None

        tokens = market_info.get("tokens", [])

        if len(tokens) < 2:
            logger.error(f"Expected 2 tokens for market {market_id}, got {len(tokens)}")
            return None

        token_id_yes = None
        token_id_no = None

        for token in tokens:
            outcome = token.get("outcome", "").lower()
            token_id = token.get("token_id")

            if "yes" in outcome or outcome == "up":
                token_id_yes = token_id
            elif "no" in outcome or outcome == "down":
                token_id_no = token_id

        if not token_id_yes or not token_id_no:
            logger.error(f"Could not identify YES/NO tokens for market {market_id}")
            return None

        self.supabase.table("markets").update({
            "token_id_yes": token_id_yes,
            "token_id_no": token_id_no
        }).eq("market_id", market_id).execute()

        logger.info(f"Token IDs - YES: {token_id_yes}, NO: {token_id_no}")

        return {
            "yes": token_id_yes,
            "no": token_id_no
        }

    async def detect_full_market_info(self) -> Optional[Dict[str, Any]]:
        event = await self.detect_current_event()

        if not event:
            return None

        event_id = event.get("id")

        await asyncio.sleep(config.API_RATE_LIMIT_DELAY)

        market = await self.detect_current_market(event_id)

        if not market:
            return None

        market_id = market.get("conditionId")

        await asyncio.sleep(config.API_RATE_LIMIT_DELAY)

        token_ids = await self.fetch_token_ids(market_id)

        if not token_ids:
            return None

        return {
            "event_id": event_id,
            "event_title": event.get("title"),
            "market_id": market_id,
            "market_question": market.get("question"),
            "token_id_yes": token_ids["yes"],
            "token_id_no": token_ids["no"]
        }
