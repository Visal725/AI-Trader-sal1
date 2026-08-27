# mt5_ai_trader

An AI-assisted trading bot for MetaTrader 5: technical-indicator + ML signal
generation, full risk management (position sizing, SL/TP, trailing stops,
daily loss limit, max-drawdown kill switch), a news blackout filter,
backtesting, and optional online (incremental) learning.

## ⚠️ Read this first

- **No trading system can guarantee profit.** Backtest results do not
  guarantee future performance, and markets can move against any strategy.
  You can lose money, including more than you intend to risk.
- `config.DEMO_MODE` defaults to `True`. `main.py live` will warn loudly if
  you try to run against a real-money account without passing
  `--confirm-live`, but **you** are responsible for confirming which account
  is connected in the MT5 terminal before running this.
- Test on a demo account for an extended period before ever considering
  real funds. Start with the smallest position sizes your broker allows.
- This is a software project, not financial advice.

## Requirements

- Windows (or Wine) with the MetaTrader 5 terminal installed and a broker
  account (demo or live) already logged in once manually.
- Python 3.10+
- `pip install -r requirements.txt`

## Setup

1. Copy `.env.example` to `.env` (create one — see `config.py` for the
   variables it reads: `MT5_LOGIN`, `MT5_PASSWORD`, `MT5_SERVER`,
   `MT5_TERMINAL_PATH`, `DEMO_MODE`).
2. Open the MT5 terminal once and log into the account you intend to use,
   so the terminal has cached the connection.
3. Adjust `config.py` — symbols, timeframe, risk %, indicator periods,
   model type — to taste.

## Usage

```bash
# 1. Train the model on historical bars pulled live from MT5
python main.py train --symbol EURUSD --bars 5000

# 2. Backtest the saved model before risking anything
python main.py backtest --symbol EURUSD --bars 5000 --balance 10000

# 3. Run the live/demo loop (trades the account currently logged into MT5)
python main.py live
# add --confirm-live only once you deliberately intend real-money orders
```

Repeat `train`/`backtest` per symbol in `config.SYMBOLS` — each symbol gets
its own saved model under `models/`.

## Project layout

```
mt5_ai_trader/
├── config.py              # all tunables; secrets via .env
├── main.py                # CLI: train / backtest / live
├── core/
│   ├── mt5_connector.py       # MT5 terminal I/O (rates, orders, positions)
│   ├── technical_indicators.py# EMA/RSI/MACD/BB/ATR/Stochastic/ADX
│   ├── risk_manager.py        # sizing, SL/TP, trailing stop, kill switches
│   ├── trade_logger.py        # CSV trade + signal logs, summary stats
│   └── news_filter.py         # high-impact news blackout windows
├── ai/
│   ├── feature_engineering.py # builds the ML feature matrix + labels
│   ├── models.py               # xgboost/random_forest/logistic wrapper
│   ├── hyperparameter_tuning.py# RandomizedSearchCV w/ TimeSeriesSplit
│   └── online_learner.py       # incremental SGD updates between retrains
├── engine/
│   ├── backtest_engine.py     # bar-by-bar simulation + performance stats
│   └── signal_generator.py    # combines rules + model confidence -> signal
└── utils/
    └── helpers.py              # logging, Telegram alerts, pip math, etc.
```

## How a trade actually gets taken

1. `main.py live` pulls fresh bars per symbol on each new-bar tick.
2. `technical_indicators.add_all_indicators` computes the indicator set.
3. `SignalGenerator` requires the rule filters (trend/RSI/ADX regime) AND
   the trained model's class probability to agree above
   `config.MIN_MODEL_CONFIDENCE` before returning BUY/SELL.
4. `RiskManager` checks daily loss limit, max drawdown, spread, and open
   position caps; then computes SL/TP from ATR and the position size from
   your risk-per-trade %.
5. `MT5Connector.place_order` sends the order with that SL and TP attached
   — the take-profit is set on every trade at entry, not added later.
6. While positions are open, the live loop tightens the stop with an
   ATR-based trailing stop (never loosens it) each cycle.
7. Everything is written to `logs/trades.csv` and `logs/signals.csv` for
   review.

## Notes on the AI model

`ai/models.py` predicts a 3-class label (down / flat / up) over the next
`config.FUTURE_BARS_LABEL` bars using `config.LABEL_THRESHOLD_PCT` as the
move-size cutoff. It's a starting point, not a guarantee of edge — validate
thoroughly with `backtest`, and consider walk-forward retraining
(`RETRAIN_EVERY_N_BARS`) rather than trusting one static model indefinitely.
`ai/online_learner.py` is provided for incremental adaptation between full
retrains but should be monitored, not left fully unsupervised.
