import asyncio
import logging
from typing import Dict, List
from decimal import Decimal
from datetime import datetime
from supabase import Client

from orderbook_manager import OrderBookManager

logger = logging.getLogger(__name__)


class PnLTracker:
    def __init__(self, supabase_client: Client, orderbook_manager: OrderBookManager):
        self.supabase = supabase_client
        self.orderbook_manager = orderbook_manager

    def _get_config(self) -> Dict:
        result = self.supabase.table("trading_config").select("*").limit(1).execute()
        logger.info(f"Config Result: {result}")
        if result.data:
            return result.data[0]
        return None

    async def update_unrealized_pnl(self):
        positions_result = self.supabase.table("positions").select("*").eq("status", "open").execute()

        if not positions_result.data:
            return

        for position in positions_result.data:
            market_id = position["market_id"]

            market_result = self.supabase.table("markets").select("*").eq("market_id", market_id).execute()

            if not market_result.data:
                continue

            market = market_result.data[0]
            outcome = position["outcome"].lower()
            token_id = market["token_id_yes"] if outcome == "yes" else market["token_id_no"]

            orderbook = await self.orderbook_manager.get_orderbook(token_id)

            if not orderbook:
                continue

            current_price = orderbook.get_best_bid()

            if not current_price:
                continue

            size = Decimal(str(position["size"]))
            cost = Decimal(str(position["cost"]))
            current_value = size * current_price
            unrealized_pnl = current_value - cost

            self.supabase.table("positions").update({
                "current_price": float(current_price),
                "unrealized_pnl": float(unrealized_pnl),
                "updated_at": datetime.utcnow().isoformat()
            }).eq("id", position["id"]).execute()

            logger.debug(f"Updated unrealized PnL for position {position['id']}: "
                        f"{unrealized_pnl} (current_price={current_price})")

    def get_current_stats(self) -> Dict:
        cfg = self._get_config()

        if not cfg:
            return {
                "balance": 0,
                "initial_balance": 0,
                "realized_pnl": 0,
                "unrealized_pnl": 0,
                "total_pnl": 0,
                "total_trades": 0,
                "open_positions": 0
            }

        balance = Decimal(str(cfg["balance"]))
        initial_balance = Decimal(str(cfg["initial_balance"]))

        positions_result = self.supabase.table("positions").select("*").eq("status", "open").execute()
        unrealized_pnl = Decimal("0")

        if positions_result.data:
            for pos in positions_result.data:
                if pos.get("unrealized_pnl"):
                    unrealized_pnl += Decimal(str(pos["unrealized_pnl"]))

        closed_positions_result = self.supabase.table("positions").select("realized_pnl").eq("status", "closed").execute()
        realized_pnl = Decimal("0")

        if closed_positions_result.data:
            for pos in closed_positions_result.data:
                if pos.get("realized_pnl"):
                    realized_pnl += Decimal(str(pos["realized_pnl"]))

        total_pnl = realized_pnl + unrealized_pnl

        trades_result = self.supabase.table("trades").select("id").execute()
        total_trades = len(trades_result.data) if trades_result.data else 0

        open_positions_count = len(positions_result.data) if positions_result.data else 0

        return {
            "balance": float(balance),
            "initial_balance": float(initial_balance),
            "realized_pnl": float(realized_pnl),
            "unrealized_pnl": float(unrealized_pnl),
            "total_pnl": float(total_pnl),
            "total_trades": total_trades,
            "open_positions": open_positions_count,
            "daily_trades": cfg["daily_trade_count"]
        }

    def record_snapshot(self):
        stats = self.get_current_stats()

        snapshot_data = {
            "balance": stats["balance"],
            "realized_pnl": stats["realized_pnl"],
            "unrealized_pnl": stats["unrealized_pnl"],
            "total_pnl": stats["total_pnl"],
            "trade_count": stats["total_trades"]
        }

        self.supabase.table("pnl_history").insert(snapshot_data).execute()

    def print_stats(self):
        stats = self.get_current_stats()


        logger.info("=" * 60)
        logger.info("TRADING STATISTICS")
        logger.info("=" * 60)
        logger.info(f"Current Balance:    ${stats['balance']:.2f}")
        logger.info(f"Initial Balance:    ${stats['initial_balance']:.2f}")
        logger.info(f"Realized PnL:       ${stats['realized_pnl']:.2f}")
        logger.info(f"Unrealized PnL:     ${stats['unrealized_pnl']:.2f}")
        logger.info(f"Total PnL:          ${stats['total_pnl']:.2f}")
        logger.info(f"Total Trades:       {stats['total_trades']}")
        logger.info(f"Open Positions:     {stats['open_positions']}")
        logger.info(f"Daily Trades:       {stats['daily_trades']}/{100}")
        logger.info("=" * 60)

    def get_trade_history(self, limit: int = 10) -> List[Dict]:
        result = self.supabase.table("trades").select("*").order("executed_at", desc=True).limit(limit).execute()
        return result.data if result.data else []

    def get_position_history(self, limit: int = 10) -> List[Dict]:
        result = self.supabase.table("positions").select("*").order("opened_at", desc=True).limit(limit).execute()
        return result.data if result.data else []
