from supabase import create_client, Client
from datetime import date, datetime
from typing import Optional, Dict, List
import logging

logger = logging.getLogger(__name__)


class Database:
    def __init__(self, supabase_url: str, supabase_key: str):
        self.client: Client = create_client(supabase_url, supabase_key)

    def initialize_bot_state(self) -> Dict:
        try:
            response = (
                self.client.table('bot_state')
                .select('*')
                .execute()
            )

            if response.data and len(response.data) > 0:
                return response.data[0]

            initial_state = {
                'balance': 1000,
                'daily_trades': 0,
                'total_trades': 0,
                'last_reset_date': str(date.today()),
                'is_running': False
            }

            response = self.client.table('bot_state').insert(initial_state).execute()
            return response.data[0]

        except Exception as e:
            logger.error(f"Error initializing bot state: {e}")
            raise

    def get_bot_state(self) -> Optional[Dict]:
        try:
            response = (
                self.client.table('bot_state')
                .select('*')
                .execute()
            )
            if response.data:
               return response.data[0]
               return None
        except Exception as e:
            logger.error(f"Error getting bot state: {e}")
            return None

    def update_bot_state(self, updates: Dict) -> bool:
        try:
            response = (
                self.client.table('bot_state')
                .select('id')
                .maybe_single()
                .execute()
            )

            if not response.data:
                return False

            bot_id = response.data['id']
            updates['updated_at'] = datetime.utcnow().isoformat()

            self.client.table('bot_state').update(updates).eq('id', bot_id).execute()
            return True
        except Exception as e:
            logger.error(f"Error updating bot state: {e}")
            return False

    def reset_daily_trades_if_needed(self) -> bool:
        try:
            state = self.get_bot_state()
            if not state:
                return False

            today = str(date.today())
            last_reset = state.get('last_reset_date')

            if last_reset != today:
                return self.update_bot_state({
                    'daily_trades': 0,
                    'last_reset_date': today
                })

            return True
        except Exception as e:
            logger.error(f"Error resetting daily trades: {e}")
            return False

    def has_traded_event(self, event_id: str) -> bool:
        try:
            response = (
                self.client.table('events')
                .select('traded')
                .eq('event_id', event_id)
                .maybe_single()
                .execute()
            )

            if response.data:
                return response.data.get('traded', False)
            return False
        except Exception as e:
            logger.error(f"Error checking if event traded: {e}")
            return False

    def save_event(self, event_data: Dict) -> Optional[str]:
        try:
            response = (
                self.client.table('events')
                .select('id')
                .eq('event_id', event_data['event_id'])
                .maybe_single()
                .execute()
            )

            if response.data:
                return response.data['id']

            event_record = {
                'event_id': event_data['event_id'],
                'market_id': event_data['market_id'],
                'token_id_up': event_data['token_id_up'],
                'token_id_down': event_data['token_id_down'],
                'traded': False
            }

            response = self.client.table('events').insert(event_record).execute()
            return response.data[0]['id']
        except Exception as e:
            logger.error(f"Error saving event: {e}")
            return None

    def mark_event_traded(self, event_id: str) -> bool:
        try:
            self.client.table('events').update({
                'traded': True,
                'updated_at': datetime.utcnow().isoformat()
            }).eq('event_id', event_id).execute()
            return True
        except Exception as e:
            logger.error(f"Error marking event as traded: {e}")
            return False

    def create_trade(self, trade_data: Dict) -> Optional[str]:
        try:
            response = self.client.table('trades').insert(trade_data).execute()
            return response.data[0]['id']
        except Exception as e:
            logger.error(f"Error creating trade: {e}")
            return None

    def update_trade(self, trade_id: str, updates: Dict) -> bool:
        try:
            updates['updated_at'] = datetime.utcnow().isoformat()
            self.client.table('trades').update(updates).eq('id', trade_id).execute()
            return True
        except Exception as e:
            logger.error(f"Error updating trade: {e}")
            return False

    def get_pending_trades(self, event_uuid: str) -> List[Dict]:
        try:
            response = (
                self.client.table('trades')
                .select('*')
                .eq('event_id', event_uuid)
                .eq('status', 'pending')
                .execute()
            )
            return response.data
        except Exception as e:
            logger.error(f"Error getting pending trades: {e}")
            return []

    def get_all_trades(self) -> List[Dict]:
        try:
            response = self.client.table('trades').select('*').execute()
            return response.data
        except Exception as e:
            logger.error(f"Error getting all trades: {e}")
            return []

    def calculate_pnl(self) -> Dict:
        try:
            trades = self.get_all_trades()
            state = self.get_bot_state()

            total_trades = len(trades)
            trades_won = len([t for t in trades if t['status'] == 'won'])
            trades_lost = len([t for t in trades if t['status'] == 'lost'])
            trades_open = len([t for t in trades if t['status'] in ['pending', 'filled']])

            total_profit = sum(t.get('profit_loss', 0) for t in trades if t.get('profit_loss', 0) > 0)
            total_loss = sum(abs(t.get('profit_loss', 0)) for t in trades if t.get('profit_loss', 0) < 0)
            net_pnl = sum(t.get('profit_loss', 0) for t in trades if t.get('profit_loss') is not None)

            current_balance = state.get('balance', 1000) if state else 1000
            initial_balance = 1000
            return_pct = ((current_balance - initial_balance) / initial_balance) * 100

            return {
                'total_trades': total_trades,
                'trades_won': trades_won,
                'trades_lost': trades_lost,
                'trades_open': trades_open,
                'win_rate': (trades_won / total_trades * 100) if total_trades > 0 else 0,
                'total_profit': total_profit,
                'total_loss': total_loss,
                'net_pnl': net_pnl,
                'current_balance': current_balance,
                'initial_balance': initial_balance,
                'return_percentage': return_pct
            }
        except Exception as e:
            logger.error(f"Error calculating PnL: {e}")
            return {}