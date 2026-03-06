import os
import time
import logging
import signal
import sys
from dotenv import load_dotenv
from database import Database
from polymarket_client import PolymarketClient
from trading_strategy import TradingStrategy
from pnl_reporter import PnLReporter

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class TradingBot:
    def __init__(self):
        load_dotenv()

        supabase_url = os.getenv('SUPABASE_URL')
        supabase_key = os.getenv('SUPABASE_KEY')

        if not supabase_url or not supabase_key:
            raise ValueError("SUPABASE_URL and SUPABASE_KEY must be set in .env file")

        self.db = Database(supabase_url, supabase_key)
        self.polymarket = PolymarketClient()
        self.strategy = TradingStrategy(self.db, self.polymarket)
        self.reporter = PnLReporter(self.db)
        self.running = False
        self.max_daily_trades = 100

        signal.signal(signal.SIGINT, self.handle_shutdown)
        signal.signal(signal.SIGTERM, self.handle_shutdown)

    def handle_shutdown(self, signum, frame):
        logger.info("\nShutdown signal received. Stopping bot...")
        self.running = False

    def start(self):
        logger.info("="*60)
        logger.info("POLYMARKET TRADING BOT - STARTING")
        logger.info("="*60)

        state = self.db.initialize_bot_state()
        logger.info(f"Bot initialized with balance: ${state['balance']:.2f}")
        logger.info(f"Max daily trades: {self.max_daily_trades}")
        logger.info("")

        self.db.update_bot_state({'is_running': True})
        self.running = True

        try:
            self.run_trading_loop()
        except Exception as e:
            logger.error(f"Fatal error in trading loop: {e}")
        finally:
            self.shutdown()

    def run_trading_loop(self):
        while self.running:
            try:
                self.db.reset_daily_trades_if_needed()

                state = self.db.get_bot_state()
                if not state:
                    logger.error("Could not retrieve bot state")
                    time.sleep(10)
                    continue

                if state['daily_trades'] >= self.max_daily_trades:
                    logger.info(f"Max daily trades reached ({self.max_daily_trades}). Stopping for today.")
                    self.running = False
                    break

                if state['balance'] < 20:
                    logger.warning(f"Insufficient balance (${state['balance']:.2f}). Stopping bot.")
                    self.running = False
                    break

                logger.info(f"Daily trades: {state['daily_trades']}/{self.max_daily_trades}, Balance: ${state['balance']:.2f}")

                logger.info("Detecting Bitcoin 15-min market...")
                market_data = self.polymarket.detect_market()

                if not market_data:
                    logger.info("No active market found. Retrying in 10 seconds...")
                    time.sleep(10)
                    continue

                logger.info(f"Found market: {market_data['event_title']}")
                logger.info(f"Event ID: {market_data['event_id']}")
                logger.info(f"Market ID: {market_data['market_id']}")

                if self.db.has_traded_event(market_data['event_id']):
                    logger.info("Already traded this event. Waiting for next event...")
                    time.sleep(10)
                    continue

                event_uuid = self.db.save_event(market_data)
                if not event_uuid:
                    logger.error("Failed to save event to database")
                    time.sleep(10)
                    continue

                logger.info("Executing trade strategy...")
                success = self.strategy.execute_trade(market_data, event_uuid)

                if success:
                    logger.info("Trade executed successfully!")
                else:
                    logger.warning("Trade execution failed")

                logger.info("Waiting for next market (10 seconds)...")
                time.sleep(10)

            except KeyboardInterrupt:
                logger.info("\nKeyboard interrupt received")
                self.running = False
                break
            except Exception as e:
                logger.error(f"Error in trading loop: {e}")
                time.sleep(10)

    def shutdown(self):
        logger.info("\n" + "="*60)
        logger.info("SHUTTING DOWN BOT")
        logger.info("="*60)

        self.db.update_bot_state({'is_running': False})

        logger.info("Generating final P&L report...")
        self.reporter.print_summary()

        logger.info("Bot stopped successfully")


def main():
    try:
        bot = TradingBot()
        bot.start()
    except KeyboardInterrupt:
        logger.info("\nBot stopped by user")
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
