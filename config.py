"""
Central configuration for mt5_ai_trader.
All secrets are pulled from environment variables (.env) — never hardcode
account credentials in source control.
"""
import os
from dotenv import load_dotenv

load_dotenv()

# ---------------------------------------------------------------------------
# MT5 ACCOUNT
# ---------------------------------------------------------------------------
MT5_LOGIN = int(os.getenv("MT5_LOGIN", "0"))
MT5_PASSWORD = os.getenv("MT5_PASSWORD", "")
MT5_SERVER = os.getenv("MT5_SERVER", "")
MT5_TERMINAL_PATH = os.getenv("MT5_TERMINAL_PATH", "")  # e.g. C:/Program Files/MetaTrader 5/terminal64.exe

# Set to True until you have verified the strategy on a demo account for
# an extended period. main.py refuses to place live orders while this is True
# unless you explicitly override with --confirm-live on the command line.
DEMO_MODE = os.getenv("DEMO_MODE", "true").lower() == "true"

# ---------------------------------------------------------------------------
# MARKET / DATA
# ---------------------------------------------------------------------------
SYMBOLS = ["EURUSDm", "GBPUSDm", "USDJPYm", "XAUUSDm"]
TIMEFRAME = "M15"          # M1, M5, M15, M30, H1, H4, D1
LOOKBACK_BARS = 1500        # bars pulled per fetch, for indicators + AI features
POLL_SECONDS = 60           # how often the main loop checks for a new bar

# ---------------------------------------------------------------------------
# RISK MANAGEMENT
# ---------------------------------------------------------------------------
RISK_PER_TRADE_PCT = 0.5      # % of equity risked per trade
MAX_DAILY_LOSS_PCT = 3.0      # stop trading for the day once hit
MAX_TOTAL_DRAWDOWN_PCT = 10.0 # kill switch - flatten & halt bot
MAX_OPEN_POSITIONS = 3
MAX_POSITIONS_PER_SYMBOL = 1
ATR_PERIOD = 14
ATR_SL_MULTIPLIER = 1.5       # stop loss = entry -/+ ATR * multiplier
ATR_TP_MULTIPLIER = 3.0       # take profit = entry -/+ ATR * multiplier (2:1 RR default)
USE_TRAILING_STOP = True
TRAILING_ATR_MULTIPLIER = 1.2
MAX_SPREAD_POINTS = 30        # skip entries if spread is too wide

# ---------------------------------------------------------------------------
# INDICATORS
# ---------------------------------------------------------------------------
EMA_FAST = 12
EMA_SLOW = 26
RSI_PERIOD = 14
RSI_OVERBOUGHT = 70
RSI_OVERSOLD = 30
MACD_FAST, MACD_SLOW, MACD_SIGNAL = 12, 26, 9
BB_PERIOD = 20
BB_STD = 2.0
ADX_PERIOD = 14
ADX_TREND_THRESHOLD = 20      # below this, market considered range-bound

# ---------------------------------------------------------------------------
# AI MODEL
# ---------------------------------------------------------------------------
MODEL_TYPE = "xgboost"        # "xgboost" | "random_forest" | "logistic"
MODEL_DIR = "models"
FUTURE_BARS_LABEL = 5         # bars ahead used to define the training label
LABEL_THRESHOLD_PCT = 0.05    # % move required to count as up/down vs. flat
MIN_MODEL_CONFIDENCE = 0.58   # probability threshold to act on a signal
RETRAIN_EVERY_N_BARS = 500
ONLINE_LEARNING_ENABLED = True

# ---------------------------------------------------------------------------
# NEWS FILTER
# ---------------------------------------------------------------------------
NEWS_FILTER_ENABLED = True
NEWS_BLACKOUT_MINUTES_BEFORE = 30
NEWS_BLACKOUT_MINUTES_AFTER = 30
# Fallback static high-impact blackout windows (UTC, "HH:MM") used if no
# calendar feed is configured — typical NFP/CPI release times, edit freely.
STATIC_NEWS_WINDOWS_UTC = ["12:30", "14:00"]

# ---------------------------------------------------------------------------
# LOGGING
# ---------------------------------------------------------------------------
LOG_DIR = "logs"
TRADE_LOG_CSV = os.path.join(LOG_DIR, "trades.csv")
SIGNAL_LOG_CSV = os.path.join(LOG_DIR, "signals.csv")
APP_LOG_FILE = os.path.join(LOG_DIR, "app.log")

MAGIC_NUMBER = 990011
