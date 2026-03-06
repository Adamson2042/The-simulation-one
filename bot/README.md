# Polymarket Bitcoin Trading Bot

A Python bot that simulates trading on Polymarket's "Bitcoin 15 minutes up or down" markets. The bot uses a systematic strategy to place simulated trades and tracks performance using a Supabase database.

## Features

- Automatically detects active Bitcoin 15-minute markets on Polymarket
- Implements a dual-position entry strategy (buy both up and down at 5% odds)
- Simulates order fills and trade outcomes
- Tracks all trades and calculates comprehensive P&L metrics
- Persists data in Supabase for analysis
- Maximum 100 trades per day with a starting balance of $1000

## Strategy Overview

### Market Detection
1. Queries Polymarket's Gamma API to find active "Bitcoin 15 minutes up or down" events
2. Retrieves the market ID for the current event
3. Fetches token IDs from the CLOB API for both outcomes (up/down)
4. Retries every 10 seconds if no active market is found

### Trading Logic
1. Places simulated buy limit orders for both UP and DOWN at 5% odds ($10 each)
2. Simulates which order gets filled based on current market prices
3. When one order fills:
   - Opens a sell limit order at 15% odds for the filled position
   - Closes the unfilled buy order
4. Holds position until simulated conclusion
5. Only trades each event once
6. Stops after 100 trades per day or when balance is insufficient

### P&L Calculation
- Total number of trades taken
- Win/loss ratio
- Total profit and loss amounts
- Net P&L and return percentage
- Current balance tracking

## Prerequisites

- Python 3.8 or higher
- Supabase account (database is already configured)
- Internet connection to access Polymarket APIs

## Installation

1. Navigate to the bot directory:
```bash
cd bot
```

2. Install required dependencies:
```bash
pip install -r requirements.txt
```

3. Create a `.env` file with your Supabase credentials:
```bash
cp .env.example .env
```

4. Edit the `.env` file and add your Supabase credentials:
```
SUPABASE_URL=your_supabase_url
SUPABASE_KEY=your_supabase_anon_key
```

## Usage

### Starting the Bot

Run the bot with:
```bash
python bot.py
```

The bot will:
- Initialize with a $1000 simulated balance
- Start monitoring for Bitcoin 15-minute markets
- Execute trades automatically based on the strategy
- Display real-time logs of all actions

### Stopping the Bot

Press `Ctrl+C` to stop the bot gracefully. The bot will:
- Complete any in-progress operations
- Generate a final P&L report
- Update the database state

### Viewing Performance

The bot automatically generates a performance report when stopped, showing:
- Trade summary (total, won, lost, open)
- Win rate percentage
- Financial summary (balance, profit, loss, P&L)
- Overall return percentage

## Database Schema

The bot uses three main tables:

### `bot_state`
Tracks the bot's current state including balance, daily trades, and running status.

### `events`
Records all detected Polymarket events with their market and token IDs.

### `trades`
Stores individual trade details including entry/exit prices, status, and P&L.

## Configuration

Key parameters can be adjusted in `trading_strategy.py`:

- `trade_amount`: Amount to invest per position (default: $10)
- `entry_odds`: Target buy price as percentage (default: 0.05 = 5%)
- `exit_odds`: Target sell price as percentage (default: 0.15 = 15%)

In `bot.py`:
- `max_daily_trades`: Maximum trades per day (default: 100)
- Initial balance: Set in database initialization (default: $1000)

## Simulation Details

This bot simulates trades rather than executing real orders:

- Order fills are simulated based on current market prices
- Trade outcomes are determined probabilistically (55% win rate by default)
- No real money is used or at risk
- All data is for analysis and backtesting purposes only

## API References

The bot uses public Polymarket APIs:

- **Gamma API**: https://gamma-api.polymarket.com (event and market data)
- **CLOB API**: https://clob.polymarket.com (order book and token data)

No API keys or authentication required for these public endpoints.

## Logging

The bot provides detailed logging including:
- Market detection status
- Trade execution details
- Balance and trade count updates
- Error messages and warnings
- Final P&L report

Logs are output to the console with timestamps.

## Troubleshooting

**Bot can't find markets:**
- Ensure Bitcoin 15-minute markets are currently active on Polymarket
- Check your internet connection
- The bot will retry every 10 seconds automatically

**Database connection errors:**
- Verify your Supabase credentials in the `.env` file
- Ensure your Supabase project is active
- Check that the database schema has been properly migrated

**Balance insufficient:**
- The bot stops when balance drops below $20
- Reset by updating the `bot_state` table in Supabase

## Disclaimer

This is a simulation bot for educational and analysis purposes only. It does not execute real trades or handle real money. Any decisions based on this bot's performance are at your own risk.
