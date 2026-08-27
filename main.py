"""
mt5_ai_trader — entry point.

Modes:
  python main.py train    --symbol EURUSD --bars 5000
  python main.py backtest --symbol EURUSD --bars 5000
  python main.py live     [--confirm-live]

`train` pulls history from MT5, builds indicators + features, trains the
configured model, and saves it to models/.

`backtest` runs the saved model bar-by-bar over historical data and prints
performance metrics (win rate, profit factor, max drawdown, Sharpe).

`live` connects to MT5, loads the saved model, and trades continuously —
checking risk limits and the news filter before every entry, managing
SL/TP/trailing stops on open positions, and logging every trade.
"""
import sys
import time
import argparse
from datetime import datetime, timezone

import pandas as pd

import config
from utils.helpers import setup_logger, send_telegram_message, is_new_bar
from core.mt5_connector import MT5Connector
from core.technical_indicators import add_all_indicators
from core.risk_manager import RiskManager
from core.trade_logger import TradeLogger
from core.news_filter import NewsFilter
from ai.models import AITradingModel
from ai.feature_engineering import build_feature_matrix
from ai.online_learner import OnlineLearner
from engine.signal_generator import SignalGenerator
from engine.backtest_engine import BacktestEngine

logger = setup_logger()


# ---------------------------------------------------------------------------
def cmd_train(args):
    conn = MT5Connector()
    conn.connect()
    raw = conn.get_rates(args.symbol, config.TIMEFRAME, args.bars)
    conn.disconnect()

    df = add_all_indicators(raw)
    X, y, feature_cols = build_feature_matrix(df, for_training=True)
    if y is None:
        raise ValueError("Training labels could not be generated from the supplied data.")
    logger.info("Training set: %d rows, %d features. Label distribution:\n%s",
                len(X), len(feature_cols), y.value_counts().to_string())

    model = AITradingModel()
    metrics = model.train(X, y)
    model.save()
    logger.info("Training complete. Test accuracy: %.4f", metrics["accuracy"])


def cmd_backtest(args):
    conn = MT5Connector()
    conn.connect()
    raw = conn.get_rates(args.symbol, config.TIMEFRAME, args.bars)
    conn.disconnect()

    model = AITradingModel()
    model.load()

    engine = BacktestEngine(initial_balance=args.balance)
    result = engine.run(raw, model)

    print("\n===== BACKTEST RESULTS:", args.symbol, "=====")
    for k, v in result.metrics.items():
        print(f"{k:>20}: {v}")

    out_path = f"logs/backtest_{args.symbol}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
    result.trades.to_csv(out_path, index=False)
    print(f"\nTrade log saved to {out_path}")


def cmd_live(args):
    if config.DEMO_MODE and not args.confirm_live:
        logger.warning(
            "DEMO_MODE=True in config.py. Running against the connected account "
            "as-is (this is safe if that account IS a demo account). "
            "If you intend this to place LIVE real-money trades on a non-demo "
            "account, re-run with --confirm-live once you have validated the "
            "strategy thoroughly."
        )

    conn = MT5Connector()
    if not conn.connect():
        logger.critical("Could not connect to MT5. Exiting.")
        sys.exit(1)

    models = {}
    for symbol in config.SYMBOLS:
        m = AITradingModel()
        try:
            m.load()
        except FileNotFoundError:
            logger.error("No trained model found for %s config. Run `train` first.", symbol)
            sys.exit(1)
        models[symbol] = m

    risk_mgr = RiskManager()
    trade_log = TradeLogger()
    news = NewsFilter()
    online_learner = OnlineLearner().load()

    last_bar_time = {s: None for s in config.SYMBOLS}

    logger.info("Live loop starting. Symbols=%s Timeframe=%s", config.SYMBOLS, config.TIMEFRAME)

    while True:
        try:
            account = conn.get_account_info()
            equity = account.get("equity", 0.0)

            if risk_mgr.max_drawdown_hit(equity):
                logger.critical("Max drawdown breached — flattening all positions and halting.")
                positions = conn.get_open_positions()
                for _, pos in positions.iterrows():
                    conn.close_position(pos.to_dict())
                send_telegram_message("🛑 mt5_ai_trader: max drawdown hit, bot halted.")
                break

            if risk_mgr.daily_loss_limit_hit(equity):
                logger.warning("Daily loss limit hit — skipping new entries until tomorrow.")
                time.sleep(config.POLL_SECONDS)
                continue

            in_blackout = news.is_news_blackout()

            for symbol in config.SYMBOLS:
                raw = conn.get_rates(symbol, config.TIMEFRAME, config.LOOKBACK_BARS)
                latest_time = raw["time"].iloc[-1]

                if not is_new_bar(last_bar_time[symbol], latest_time):
                    continue
                last_bar_time[symbol] = latest_time

                df = add_all_indicators(raw)
                generator = SignalGenerator(models[symbol])
                sig = generator.generate(symbol, df)

                trade_log.log_signal(
                    symbol=symbol, signal=sig.direction, confidence=sig.confidence,
                    rsi=df["rsi"].iloc[-1], adx=df["adx"].iloc[-1],
                    macd_hist=df["macd_hist"].iloc[-1], price=sig.price,
                )

                if sig.direction == "HOLD":
                    continue
                if in_blackout:
                    logger.info("%s: signal %s suppressed by news blackout.", symbol, sig.direction)
                    continue

                symbol_info = conn.get_symbol_info(symbol)
                if not risk_mgr.spread_acceptable(symbol_info.spread):
                    logger.info("%s: spread too wide (%d pts), skipping.", symbol, symbol_info.spread)
                    continue

                open_positions = conn.get_open_positions()
                total_open = len(open_positions)
                symbol_open = len(open_positions[open_positions["symbol"] == symbol]) if not open_positions.empty else 0

                if not risk_mgr.can_open_new_position(total_open, symbol_open):
                    continue

                sl, tp = risk_mgr.calculate_sl_tp(sig.price, sig.atr, sig.direction)
                sizing = risk_mgr.position_size(equity, sig.price, sl, symbol_info)

                if sizing.volume <= 0:
                    continue

                result = conn.place_order(
                    symbol=symbol, direction=sig.direction, volume=sizing.volume,
                    sl=sl, tp=tp, comment=f"ai-conf{sig.confidence:.2f}",
                )

                trade_log.log_trade(
                    symbol=symbol, direction=sig.direction, volume=sizing.volume,
                    entry_price=sig.price, sl=sl, tp=tp, confidence=sig.confidence,
                    reason=sig.reason, ticket=(result or {}).get("order", ""),
                    status="FILLED" if result else "REJECTED",
                )

                if result:
                    send_telegram_message(
                        f"📈 {symbol} {sig.direction} {sizing.volume} lots @ {sig.price:.5f} "
                        f"(SL {sl:.5f} / TP {tp:.5f}, conf {sig.confidence:.2f})"
                    )

            # --- manage trailing stops on open positions ---
            if config.USE_TRAILING_STOP:
                positions = conn.get_open_positions()
                for _, pos in positions.iterrows():
                    raw = conn.get_rates(pos["symbol"], config.TIMEFRAME, 50)
                    df = add_all_indicators(raw)
                    atr_val = df["atr"].iloc[-1]
                    direction = "BUY" if pos["type"] == 0 else "SELL"
                    new_sl = risk_mgr.calculate_trailing_stop(pos["price_current"], atr_val, direction)
                    better = (new_sl > pos["sl"]) if direction == "BUY" else (new_sl < pos["sl"] or pos["sl"] == 0)
                    if better:
                        conn.modify_sl_tp(int(pos["ticket"]), new_sl, pos["tp"])

            time.sleep(config.POLL_SECONDS)

        except KeyboardInterrupt:
            logger.info("Shutdown requested by user.")
            break
        except Exception as e:
            logger.exception("Unhandled error in live loop: %s", e)
            time.sleep(config.POLL_SECONDS)

    conn.disconnect()


# ---------------------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser(description="mt5_ai_trader")
    sub = parser.add_subparsers(dest="mode", required=True)

    p_train = sub.add_parser("train", help="Train the AI model on historical data")
    p_train.add_argument("--symbol", default=config.SYMBOLS[0])
    p_train.add_argument("--bars", type=int, default=5000)
    p_train.set_defaults(func=cmd_train)

    p_bt = sub.add_parser("backtest", help="Backtest the saved model")
    p_bt.add_argument("--symbol", default=config.SYMBOLS[0])
    p_bt.add_argument("--bars", type=int, default=5000)
    p_bt.add_argument("--balance", type=float, default=10_000.0)
    p_bt.set_defaults(func=cmd_backtest)

    p_live = sub.add_parser("live", help="Run the live/demo trading loop")
    p_live.add_argument("--confirm-live", action="store_true",
                         help="Acknowledge this may place real-money trades.")
    p_live.set_defaults(func=cmd_live)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
