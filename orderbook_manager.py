import asyncio
import logging
from typing import Optional, Dict, List
from decimal import Decimal
import aiohttp

import config

logger = logging.getLogger(__name__)


class OrderBook:
    def __init__(self, token_id: str):
        self.token_id = token_id
        self.bids: List[Dict] = []
        self.asks: List[Dict] = []
        self.last_update = None

    def update(self, orderbook_data: Dict):
        self.bids = orderbook_data.get("bids", [])
        self.asks = orderbook_data.get("asks", [])
        self.last_update = asyncio.get_event_loop().time()

    def get_best_bid(self) -> Optional[Decimal]:
        if not self.bids:
            return None
        return Decimal(str(self.bids[0]["price"]))

    def get_best_ask(self) -> Optional[Decimal]:
        if not self.asks:
            return None
        return Decimal(str(self.asks[0]["price"]))

    def get_liquidity_at_price(self, price: Decimal, side: str) -> Decimal:
        orders = self.bids if side == "bid" else self.asks
        total_liquidity = Decimal("0")

        for order in orders:
            order_price = Decimal(str(order["price"]))

            if side == "bid" and order_price >= price:
                total_liquidity += Decimal(str(order["size"]))
            elif side == "ask" and order_price <= price:
                total_liquidity += Decimal(str(order["size"]))

        return total_liquidity


class OrderBookManager:
    def __init__(self):
        self.session: Optional[aiohttp.ClientSession] = None
        self.orderbooks: Dict[str, OrderBook] = {}

    async def initialize(self):
        self.session = aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=config.API_REQUEST_TIMEOUT))

    async def close(self):
        if self.session:
            await self.session.close()

    async def fetch_orderbook(self, token_id: str) -> Optional[OrderBook]:
        try:
            params = {"token_id": token_id}
            async with self.session.get(config.CLOB_ORDERBOOK_ENDPOINT, params=params) as response:
                if response.status == 200:
                    data = await response.json()

                    if token_id not in self.orderbooks:
                        self.orderbooks[token_id] = OrderBook(token_id)

                    self.orderbooks[token_id].update(data)
                    logger.debug(f"Fetched orderbook for token {token_id}: "
                               f"Best bid={self.orderbooks[token_id].get_best_bid()}, "
                               f"Best ask={self.orderbooks[token_id].get_best_ask()}")

                    return self.orderbooks[token_id]
                else:
                    logger.error(f"Failed to fetch orderbook for token {token_id}: Status {response.status}")
                    return None
        except Exception as e:
            logger.error(f"Error fetching orderbook for token {token_id}: {e}")
            return None

    async def get_orderbook(self, token_id: str) -> Optional[OrderBook]:
        if token_id in self.orderbooks:
            return self.orderbooks[token_id]

        return await self.fetch_orderbook(token_id)

    async def refresh_orderbook(self, token_id: str) -> Optional[OrderBook]:
        return await self.fetch_orderbook(token_id)

    async def get_execution_price(self, token_id: str, side: str, size: Decimal) -> Optional[Dict]:
        orderbook = await self.get_orderbook(token_id)

        if not orderbook:
            logger.error(f"No orderbook available for token {token_id}")
            return None

        if side == "buy":
            best_price = orderbook.get_best_ask()
            if not best_price:
                logger.warning(f"No asks available for token {token_id}")
                return None

            available_liquidity = orderbook.get_liquidity_at_price(best_price, "ask")

            if available_liquidity >= size:
                return {
                    "price": best_price,
                    "filled_size": size,
                    "partial": False
                }
            else:
                return {
                    "price": best_price,
                    "filled_size": available_liquidity,
                    "partial": True
                }

        elif side == "sell":
            best_price = orderbook.get_best_bid()
            if not best_price:
                logger.warning(f"No bids available for token {token_id}")
                return None

            available_liquidity = orderbook.get_liquidity_at_price(best_price, "bid")

            if available_liquidity >= size:
                return {
                    "price": best_price,
                    "filled_size": size,
                    "partial": False
                }
            else:
                return {
                    "price": best_price,
                    "filled_size": available_liquidity,
                    "partial": True
                }

        return None

    async def check_limit_order_fill(self, token_id: str, side: str, limit_price: Decimal) -> bool:
        orderbook = await self.refresh_orderbook(token_id)

        if not orderbook:
            return False

        if side == "buy":
            best_ask = orderbook.get_best_ask()
            if best_ask and best_ask <= limit_price:
                logger.info(f"Buy limit order can be filled: best_ask={best_ask} <= limit_price={limit_price}")
                return True
        elif side == "sell":
            best_bid = orderbook.get_best_bid()
            if best_bid and best_bid >= limit_price:
                logger.info(f"Sell limit order can be filled: best_bid={best_bid} >= limit_price={limit_price}")
                return True

        return False
