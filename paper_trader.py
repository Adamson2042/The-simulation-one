import asyncio
import logging
from typing import Optional, Dict
from decimal import Decimal
from datetime import datetime
from supabase import Client

import config
from orderbook_manager import OrderBookManager

logger = logging.getLogger(__name__)


class PaperTrader:
    def __init__(self, supabase_client: Client, orderbook_manager: OrderBookManager):
        self.supabase = supabase_client
        self.orderbook_manager = orderbook_manager

    def _get_config(self) -> Dict:
        result = self.supabase.table("trading_config").select("*").limit(1).execute()
        if result.data:
            return result.data[0]
        return None

    def _update_config(self, updates: Dict):
        self.supabase.table("trading_config").update(updates).eq("id", self._get_config()["id"]).execute()

    def _can_trade(self) -> bool:
        cfg = self._get_config()
        if not cfg:
            logger.error("No trading config found")
            return False

        from datetime import date
        today = date.today()
        last_reset = datetime.fromisoformat(cfg["last_reset_date"]).date()

        if today > last_reset:
            self._update_config({
                "daily_trade_count": 0,
                "last_reset_date": today.isoformat()
            })
            cfg = self._get_config()

        if cfg["daily_trade_count"] >= cfg["max_daily_trades"]:
            logger.warning(f"Daily trade limit reached: {cfg['daily_trade_count']}/{cfg['max_daily_trades']}")
            return False

        if cfg["balance"] <= 0:
            logger.error("Insufficient balance to trade")
            return False

        return True

    async def place_limit_order(self, market_id: str, token_id: str, side: str,
                               outcome: str, price: Decimal, size: Decimal) -> Optional[str]:
        if not self._can_trade():
            return None

        order_data = {
            "market_id": market_id,
            "order_type": "limit",
            "side": side,
            "outcome": outcome,
            "price": float(price),
            "size": float(size),
            "status": "pending",
            "filled_size": 0
        }

        result = self.supabase.table("orders").insert(order_data).execute()

        if result.data:
            order_id = result.data[0]["id"]
            logger.info(f"Placed limit order: {side} {outcome} at {price} for size {size} (Order ID: {order_id})")
            return order_id

        return None

    async def cancel_order(self, order_id: str):
        self.supabase.table("orders").update({
            "status": "cancelled",
            "cancelled_at": datetime.utcnow().isoformat()
        }).eq("id", order_id).execute()

        logger.info(f"Cancelled order {order_id}")

    async def check_and_fill_order(self, order_id: str) -> bool:
        order_result = self.supabase.table("orders").select("*").eq("id", order_id).execute()

        if not order_result.data:
            logger.error(f"Order {order_id} not found")
            return False

        order = order_result.data[0]

        if order["status"] != "pending":
            return False

        market_result = self.supabase.table("markets").select("*").eq("market_id", order["market_id"]).execute()

        if not market_result.data:
            logger.error(f"Market {order['market_id']} not found")
            return False

        market = market_result.data[0]
        token_id = market["token_id_yes"] if order["outcome"].lower() == "yes" else market["token_id_no"]

        limit_price = Decimal(str(order["price"]))
        can_fill = await self.orderbook_manager.check_limit_order_fill(token_id, order["side"], limit_price)

        if can_fill:
            await self._execute_fill(order_id, order, token_id)
            return True

        return False

    async def _execute_fill(self, order_id: str, order: Dict, token_id: str):
        size = Decimal(str(order["size"]))
        execution = await self.orderbook_manager.get_execution_price(token_id, order["side"], size)

        if not execution:
            logger.error(f"Could not get execution price for order {order_id}")
            return

        filled_size = execution["filled_size"]
        exec_price = execution["price"]
        cost = filled_size * exec_price

        cfg = self._get_config()
        new_balance = Decimal(str(cfg["balance"])) - cost

        self.supabase.table("orders").update({
            "status": "filled",
            "filled_size": float(filled_size),
            "filled_at": datetime.utcnow().isoformat()
        }).eq("id", order_id).execute()

        trade_data = {
            "order_id": order_id,
            "market_id": order["market_id"],
            "side": order["side"],
            "outcome": order["outcome"],
            "price": float(exec_price),
            "size": float(filled_size),
            "cost": float(cost)
        }

        self.supabase.table("trades").insert(trade_data).execute()

        self._update_config({
            "balance": float(new_balance),
            "daily_trade_count": cfg["daily_trade_count"] + 1
        })

        logger.info(f"Order {order_id} filled: {order['side']} {filled_size} {order['outcome']} "
                   f"at {exec_price} (cost: {cost}, new balance: {new_balance})")

        if order["side"] == "buy":
            position_data = {
                "market_id": order["market_id"],
                "outcome": order["outcome"],
                "entry_price": float(exec_price),
                "size": float(filled_size),
                "cost": float(cost),
                "status": "open"
            }

            self.supabase.table("positions").upsert(position_data, on_conflict="market_id").execute()

    async def place_sell_order(self, market_id: str, outcome: str, price: Decimal, size: Decimal) -> Optional[str]:
        market_result = self.supabase.table("markets").select("*").eq("market_id", market_id).execute()

        if not market_result.data:
            logger.error(f"Market {market_id} not found")
            return None

        market = market_result.data[0]
        token_id = market["token_id_yes"] if outcome.lower() == "yes" else market["token_id_no"]

        return await self.place_limit_order(market_id, token_id, "sell", outcome, price, size)

    async def get_pending_orders(self, market_id: str) -> list:
        result = self.supabase.table("orders").select("*").eq("market_id", market_id).eq("status", "pending").execute()
        return result.data if result.data else []

    async def resolve_position(self, market_id: str, winning_outcome: str):
        position_result = self.supabase.table("positions").select("*").eq("market_id", market_id).eq("status", "open").execute()

        if not position_result.data:
            logger.info(f"No open position for market {market_id}")
            return

        position = position_result.data[0]
        position_outcome = position["outcome"].lower()
        size = Decimal(str(position["size"]))
        cost = Decimal(str(position["cost"]))

        if position_outcome == winning_outcome.lower():
            payout = size
            realized_pnl = payout - cost
        else:
            payout = Decimal("0")
            realized_pnl = -cost

        cfg = self._get_config()
        new_balance = Decimal(str(cfg["balance"])) + payout

        self.supabase.table("positions").update({
            "status": "closed",
            "closed_at": datetime.utcnow().isoformat(),
            "realized_pnl": float(realized_pnl)
        }).eq("id", position["id"]).execute()

        self._update_config({
            "balance": float(new_balance)
        })

        self.supabase.table("markets").update({
            "status": "resolved",
            "resolution": winning_outcome,
            "resolved_at": datetime.utcnow().isoformat()
        }).eq("market_id", market_id).execute()

        logger.info(f"Position resolved for market {market_id}: "
                   f"Outcome={position_outcome}, Winner={winning_outcome}, "
                   f"PnL={realized_pnl}, New balance={new_balance}")
