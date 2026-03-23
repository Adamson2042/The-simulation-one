import asyncio
import logging
import sys
from decimal import Decimal
from supabase import create_client

import config
from market_detector import MarketDetector
from orderbook_manager import OrderBookManager
from paper_trader import PaperTrader
from pnl_tracker import PnLTracker

logging.basicConfig(
    level=getattr(logging, config.LOG_LEVEL),
    format=config.LOG_FORMAT
)

logger = logging.getLogger(__name__)


class PolymarketTradingBot:
    def __init__(self):
        self.supabase = create_client(config.SUPABASE_URL, config.SUPABASE_KEY)
        self.market_detector = MarketDetector(self.supabase)
        self.orderbook_manager = OrderBookManager()
        self.paper_trader = PaperTrader(self.supabase, self.orderbook_manager)
        self.pnl_tracker = PnLTracker(self.supabase, self.orderbook_manager)
        self.running = False

    async def initialize(self):
        logger.info("Initializing Polymarket Trading Bot...")
        await self.market_detector.initialize()
        await self.orderbook_manager.initialize()
        logger.info("Bot initialized successfully")

    async def cleanup(self):
        logger.info("Cleaning up resources...")
        await self.market_detector.close()
        await self.orderbook_manager.close()
        logger.info("Cleanup complete")

    async def execute_trading_strategy(self, market_info: dict):
        market_id = market_info["market_id"]
        token_id_yes = market_info["token_id_yes"]
        token_id_no = market_info["token_id_no"]

        logger.info(f"Executing trading strategy for market {market_id}")
        logger.info(f"Market: {market_info['market_question']}")

        buy_price = config.BUY_LIMIT_PRICE
        stake = config.STAKE_SIZE

        size_in_shares = stake / buy_price

        logger.info(f"Placing buy limit orders at {buy_price} (${stake} each)...")

        order_yes_id = await self.paper_trader.place_limit_order(
            market_id, token_id_yes, "buy", "YES", buy_price, size_in_shares
        )

        order_no_id = await self.paper_trader.place_limit_order(
            market_id, token_id_no, "buy", "NO", buy_price, size_in_shares
        )

        if not order_yes_id or not order_no_id:
            logger.error("Failed to place initial buy orders")
            return

        logger.info(f"Orders placed - YES: {order_yes_id}, NO: {order_no_id}")

        filled_order = None
        filled_outcome = None
        unfilled_order_id = None

        logger.info("Monitoring orders for fills...")

        while True:
            await asyncio.sleep(2)

            yes_filled = await self.paper_trader.check_and_fill_order(order_yes_id)
            no_filled = await self.paper_trader.check_and_fill_order(order_no_id)

            if yes_filled:
                filled_order = order_yes_id
                filled_outcome = "YES"
                unfilled_order_id = order_no_id
                logger.info("YES order filled!")
                break
            elif no_filled:
                filled_order = order_no_id
                filled_outcome = "NO"
                unfilled_order_id = order_yes_id
                logger.info("NO order filled!")
                break

            market_result = self.supabase.table("markets").select("status").eq("market_id", market_id).execute()
            if market_result.data and market_result.data[0]["status"] != "active":
                logger.info("Market no longer active, cancelling orders")
                await self.paper_trader.cancel_order(order_yes_id)
                await self.paper_trader.cancel_order(order_no_id)
                return

        await self.paper_trader.cancel_order(unfilled_order_id)
        logger.info(f"Cancelled unfilled order: {unfilled_order_id}")

        sell_price = config.SELL_LIMIT_PRICE

        logger.info(f"Placing sell limit order for {filled_outcome} at {sell_price}...")

        sell_order_id = await self.paper_trader.place_sell_order(
            market_id, filled_outcome, sell_price, size_in_shares
        )

        if not sell_order_id:
            logger.error("Failed to place sell order")
            return

        logger.info(f"Sell order placed: {sell_order_id}")
        logger.info("Monitoring sell order and position until market resolution...")

        while True:
            await asyncio.sleep(5)

            await self.paper_trader.check_and_fill_order(sell_order_id)

            await self.pnl_tracker.update_unrealized_pnl()

            market_result = self.supabase.table("markets").select("*").eq("market_id", market_id).execute()

            if not market_result.data:
                continue

            market = market_result.data[0]

            if market["status"] == "resolved":
                logger.info(f"Market resolved! Winner: {market['resolution']}")

                await self.paper_trader.cancel_order(sell_order_id)

                await self.paper_trader.resolve_position(market_id, market["resolution"])

                self.supabase.table("events").update({
                    "traded": True,
                    "status": "completed"
                }).eq("event_id", market_info["event_id"]).execute()

                self.pnl_tracker.record_snapshot()
                self.pnl_tracker.print_stats()

                break

    async def run(self):
        self.running = True
        logger.info("Starting Polymarket Paper Trading Bot")
        self.pnl_tracker.print_stats()

        while self.running:
            try:
                logger.info("Searching for BTC 5-minute markets...")

                market_info = await self.market_detector.detect_full_market_info()

                if not market_info:
                    logger.info(f"No tradable market found, retrying in {config.MARKET_DETECTION_RETRY_DELAY}s...")
                    await asyncio.sleep(config.MARKET_DETECTION_RETRY_DELAY)
                    continue

                logger.info(f"Found market: {market_info['market_question']}")

                await self.execute_trading_strategy(market_info)

                logger.info(f"Trade completed, waiting {config.TRADED_MARKET_RETRY_DELAY}s before next trade...")
                await asyncio.sleep(config.TRADED_MARKET_RETRY_DELAY)

            except KeyboardInterrupt:
                logger.info("Received interrupt signal, stopping bot...")
                self.running = False
                break
            except Exception as e:
                logger.error(f"Error in main loop: {e}", exc_info=True)
                await asyncio.sleep(config.MARKET_DETECTION_RETRY_DELAY)

        await self.cleanup()


async def main():
    if not config.SUPABASE_URL or not config.SUPABASE_KEY:
        logger.error("SUPABASE_URL and SUPABASE_ANON_KEY environment variables must be set")
        sys.exit(1)

    bot = PolymarketTradingBot()

    try:
        await bot.initialize()
        await bot.run()
    except KeyboardInterrupt:
        logger.info("Bot stopped by user")
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
    finally:
        await bot.cleanup()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Exiting...")
