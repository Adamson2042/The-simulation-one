# Polymarket Paper Trading Bot

A Python-based paper trading bot for Polymarket that simulates real trading using live market data from Bitcoin 5-minute up/down markets.

## Features

- **Real Market Data**: Uses actual Polymarket API data, not random simulations
- **Real-time Order Books**: Fetches and monitors live order book data from Polymarket CLOB API
- **Paper Trading**: Simulates trades without risking real money
- **Automated Market Detection**: Automatically finds and tracks BTC 5-minute markets
- **Smart Order Execution**: Simulates limit orders with realistic fill logic based on liquidity
- **PnL Tracking**: Real-time profit/loss tracking with historical snapshots
- **Database Persistence**: All trades, positions, and statistics stored in Supabase

## Architecture

The bot is built with a modular structure:

- **config.py**: Configuration settings and API endpoints
- **market_detector.py**: Detects BTC 5-minute markets using Polymarket Gamma API
- **orderbook_manager.py**: Fetches and manages real-time order book data from CLOB API
- **paper_trader.py**: Simulates trade execution using real order book prices
- **pnl_tracker.py**: Tracks realized and unrealized profit/loss
- **main.py**: Main execution loop and trading strategy

## Trading Strategy

The bot implements a simple market-making strategy:

1. **Initial Orders**: Places buy limit orders for both YES and NO outcomes at 5% odds ($10 each)
2. **Order Fill**: Monitors order book until one order gets filled
3. **Exit Strategy**: When filled, places a sell limit order at 15% odds and cancels the other buy order
4. **Position Management**: Holds position until market resolves or sell order fills
5. **Risk Management**:
   - Maximum 100 trades per day
   - Tracks balance and ensures sufficient funds
   - One trade per event

## Prerequisites

- Python 3.8+
- Supabase account (database is pre-configured)
- Environment variables set in `.env` file

## Installation

1. Install Python dependencies:

```bash
pip install -r requirements.txt
```

2. Verify your `.env` file contains:

```
SUPABASE_URL=your_supabase_url
SUPABASE_ANON_KEY=your_supabase_key
```

## Usage

Run the bot:

```bash
python main.py
```

The bot will:
1. Start with a simulated balance of $1000
2. Search for active BTC 5-minute markets
3. Execute the trading strategy automatically
4. Display statistics and PnL updates
5. Continue running until stopped (Ctrl+C)

## Database Schema

The bot uses Supabase with the following tables:

- **trading_config**: Bot configuration and balance
- **events**: Detected Polymarket events
- **markets**: Market information and token IDs
- **orders**: All simulated orders
- **trades**: Executed trades
- **positions**: Open and closed positions
- **pnl_history**: Historical PnL snapshots

## API Integration

### Gamma API (Market Detection)
- Endpoint: `https://gamma-api.polymarket.com`
- Used for: Finding active events and markets
- Rate limit handling: 1-second delays between requests

### CLOB API (Order Book)
- Endpoint: `https://clob.polymarket.com`
- Used for: Real-time order book data and market information
- Provides: Best bid/ask prices, liquidity data

## How It Works

### Market Detection
1. Polls Gamma API for active events
2. Filters for Bitcoin + 5-minute keywords
3. Skips previously traded markets
4. Fetches market and token IDs from CLOB API

### Order Simulation
1. Fetches real order book for the market
2. Checks if limit orders can be filled based on best bid/ask
3. Simulates execution at actual market prices
4. Handles partial fills based on available liquidity

### Position Tracking
1. Updates unrealized PnL using live prices
2. Monitors market resolution
3. Calculates realized PnL when position closes
4. Updates balance and records statistics

## Configuration

Key settings in `config.py`:

```python
INITIAL_BALANCE = Decimal("1000")
MAX_DAILY_TRADES = 100
BUY_LIMIT_PRICE = Decimal("0.05")   # 5%
SELL_LIMIT_PRICE = Decimal("0.15")  # 15%
STAKE_SIZE = Decimal("10")
```

## Logging

The bot provides detailed logging:

- **INFO**: Market detection, order placement, fills, and statistics
- **DEBUG**: Order book updates and PnL calculations
- **ERROR**: API failures and critical issues

## Safety Features

- **No Real Trading**: All trades are simulated, no actual money at risk
- **Balance Tracking**: Prevents trading with insufficient funds
- **Daily Limits**: Maximum 100 trades per day
- **Error Handling**: Robust error handling for API failures
- **Rate Limiting**: Respects API rate limits with delays

## Monitoring

The bot displays real-time statistics:

```
==========================================================
TRADING STATISTICS
==========================================================
Current Balance:    $1015.50
Initial Balance:    $1000.00
Realized PnL:       $15.50
Unrealized PnL:     $2.30
Total PnL:          $17.80
Total Trades:       4
Open Positions:     1
Daily Trades:       4/100
==========================================================
```

## Troubleshooting

**No markets found**
- BTC 5-minute markets may not be active
- Check Polymarket website for available markets
- Bot will retry every 10 seconds

**Orders not filling**
- Order book may not have sufficient liquidity at limit prices
- Adjust BUY_LIMIT_PRICE and SELL_LIMIT_PRICE in config.py

**API errors**
- Check internet connection
- Verify Polymarket APIs are accessible
- Bot will automatically retry with delays

## Notes

- This is a paper trading bot for educational purposes
- Uses real market data but no actual trades are executed
- All outcomes are determined by actual market resolution, not random numbers
- Simulated balance starts at $1000 and is tracked in the database

## License

This project is for educational purposes only. Use at your own risk.
