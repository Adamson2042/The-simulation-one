import logging
from typing import Dict
from database import Database

logger = logging.getLogger(__name__)


class PnLReporter:
    def __init__(self, db: Database):
        self.db = db

    def generate_report(self) -> str:
        pnl_data = self.db.calculate_pnl()

        if not pnl_data:
            return "Unable to generate PnL report"

        report_lines = [
            "\n" + "="*60,
            "TRADING BOT - PERFORMANCE REPORT",
            "="*60,
            "",
            "TRADE SUMMARY:",
            f"  Total Trades:        {pnl_data['total_trades']}",
            f"  Trades Won:          {pnl_data['trades_won']}",
            f"  Trades Lost:         {pnl_data['trades_lost']}",
            f"  Trades Open:         {pnl_data['trades_open']}",
            f"  Win Rate:            {pnl_data['win_rate']:.2f}%",
            "",
            "FINANCIAL SUMMARY:",
            f"  Initial Balance:     ${pnl_data['initial_balance']:.2f}",
            f"  Current Balance:     ${pnl_data['current_balance']:.2f}",
            f"  Total Profit:        ${pnl_data['total_profit']:.2f}",
            f"  Total Loss:          ${pnl_data['total_loss']:.2f}",
            f"  Net P&L:             ${pnl_data['net_pnl']:.2f}",
            f"  Return:              {pnl_data['return_percentage']:.2f}%",
            "",
            "="*60,
            ""
        ]

        report = "\n".join(report_lines)
        logger.info(report)
        return report

    def print_summary(self):
        print(self.generate_report())
