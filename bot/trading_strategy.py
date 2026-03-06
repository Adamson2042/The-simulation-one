import random
import logging
from typing import Dict, Optional, List
from database import Database
from polymarket_client import PolymarketClient

logger = logging.getLogger(__name__)


class TradingStrategy:
    def __init__(self, db: Database, polymarket: PolymarketClient):
        self.db = db
        self.polymarket = polymarket
        self.trade_amount = 10
        self.entry_odds = 0.05
        self.exit_odds = 0.15

    def simulate_order_fill(self, direction: str, current_price: float, target_price: float) -> bool:
        if direction == 'buy':
            if current_price <= target_price:
                return random.random() < 0.7
            else:
                return random.random() < 0.3
        else:
            if current_price >= target_price:
                return random.random() < 0.7
            else:
                return random.random() < 0.3

    def get_simulated_market_price(self, token_id: str) -> float:
        prices = self.polymarket.get_best_prices(token_id)

        if prices['bid'] and prices['ask']:
            mid_price = (prices['bid'] + prices['ask']) / 2
            return mid_price
        elif prices['bid']:
            return prices['bid']
        elif prices['ask']:
            return prices['ask']
        else:
            return random.uniform(0.45, 0.55)

    def execute_trade(self, event_data: Dict, event_uuid: str) -> bool:
        try:
            state = self.db.get_bot_state()
            if not state:
                logger.error("Could not get bot state")
                return False

            if state['balance'] < self.trade_amount * 2:
                logger.warning(f"Insufficient balance: {state['balance']}")
                return False

            token_id_up = event_data['token_id_up']
            token_id_down = event_data['token_id_down']

            trade_up = {
                'event_id': event_uuid,
                'direction': 'up',
                'entry_price': self.entry_odds,
                'amount': self.trade_amount,
                'status': 'pending'
            }

            trade_down = {
                'event_id': event_uuid,
                'direction': 'down',
                'entry_price': self.entry_odds,
                'amount': self.trade_amount,
                'status': 'pending'
            }

            trade_up_id = self.db.create_trade(trade_up)
            trade_down_id = self.db.create_trade(trade_down)

            if not trade_up_id or not trade_down_id:
                logger.error("Failed to create trade records")
                return False

            logger.info(f"Created buy orders for {event_data['event_id']}")
            logger.info(f"  UP at {self.entry_odds*100}% for ${self.trade_amount}")
            logger.info(f"  DOWN at {self.entry_odds*100}% for ${self.trade_amount}")

            current_price_up = self.get_simulated_market_price(token_id_up)
            current_price_down = self.get_simulated_market_price(token_id_down)

            logger.info(f"Current market prices - UP: {current_price_up:.4f}, DOWN: {current_price_down:.4f}")

            filled_direction = None
            filled_trade_id = None
            unfilled_trade_id = None

            if self.simulate_order_fill('buy', current_price_up, self.entry_odds):
                filled_direction = 'up'
                filled_trade_id = trade_up_id
                unfilled_trade_id = trade_down_id
                logger.info(f"UP order filled at {self.entry_odds*100}%")
            elif self.simulate_order_fill('buy', current_price_down, self.entry_odds):
                filled_direction = 'down'
                filled_trade_id = trade_down_id
                unfilled_trade_id = trade_up_id
                logger.info(f"DOWN order filled at {self.entry_odds*100}%")
            else:
                if random.random() < 0.5:
                    filled_direction = 'up'
                    filled_trade_id = trade_up_id
                    unfilled_trade_id = trade_down_id
                    logger.info(f"UP order eventually filled at {self.entry_odds*100}%")
                else:
                    filled_direction = 'down'
                    filled_trade_id = trade_down_id
                    unfilled_trade_id = trade_up_id
                    logger.info(f"DOWN order eventually filled at {self.entry_odds*100}%")

            self.db.update_trade(filled_trade_id, {'status': 'filled'})
            self.db.update_trade(unfilled_trade_id, {'status': 'closed', 'profit_loss': 0})

            new_balance = state['balance'] - self.trade_amount
            self.db.update_bot_state({'balance': new_balance})

            logger.info(f"Opened sell order for {filled_direction.upper()} at {self.exit_odds*100}%")

            logger.info(f"Position opened: {filled_direction.upper()}")
            logger.info(f"Entry: {self.entry_odds*100}%, Target: {self.exit_odds*100}%")

            self.db.mark_event_traded(event_data['event_id'])

            new_daily = state['daily_trades'] + 1
            new_total = state['total_trades'] + 1
            self.db.update_bot_state({
                'daily_trades': new_daily,
                'total_trades': new_total
            })

            self.simulate_trade_outcome(filled_trade_id, filled_direction)

            return True

        except Exception as e:
            logger.error(f"Error executing trade: {e}")
            return False

    def simulate_trade_outcome(self, trade_id: str, direction: str):
        win_probability = 0.55

        is_winner = random.random() < win_probability

        if is_winner:
            profit = self.trade_amount * (self.exit_odds - self.entry_odds) / self.entry_odds
            self.db.update_trade(trade_id, {
                'status': 'won',
                'exit_price': self.exit_odds,
                'profit_loss': profit
            })

            state = self.db.get_bot_state()
            if state:
                new_balance = state['balance'] + self.trade_amount + profit
                self.db.update_bot_state({'balance': new_balance})

            logger.info(f"Trade WON! Profit: ${profit:.2f}")
        else:
            loss = -self.trade_amount
            self.db.update_trade(trade_id, {
                'status': 'lost',
                'exit_price': 0,
                'profit_loss': loss
            })

            logger.info(f"Trade LOST! Loss: ${abs(loss):.2f}")
