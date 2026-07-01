"""
Walk-forward backtester for the SMC forex strategy.
Uses yfinance for historical OHLCV — no look-ahead bias.
"""
from __future__ import annotations

import json
import logging
import warnings
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

DATA_DIR = Path(__file__).parents[4] / "data" / "backtest"
DATA_DIR.mkdir(parents=True, exist_ok=True)

IST = timezone(timedelta(hours=5, minutes=30))

# yfinance ticker map
_YF_MAP = {
    "EURUSD": "EURUSD=X", "GBPUSD": "GBPUSD=X", "USDJPY": "JPY=X",
    "USDCHF": "CHF=X",   "AUDUSD": "AUDUSD=X", "USDCAD": "CAD=X",
    "NZDUSD": "NZDUSD=X","EURGBP": "EURGBP=X", "EURJPY": "EURJPY=X",
    "GBPJPY": "GBPJPY=X","XAUUSD": "GC=F",     "XAGUSD": "SI=F",
    "BTCUSD": "BTC-USD",  "ETHUSD": "ETH-USD",
    # crosses
    "EURAUD": "EURAUD=X", "EURCAD": "EURCAD=X", "EURCHF": "EURCHF=X",
    "EURNZD": "EURNZD=X", "GBPAUD": "GBPAUD=X", "GBPCAD": "GBPCAD=X",
    "GBPCHF": "GBPCHF=X", "GBPNZD": "GBPNZD=X",
    "AUDCAD": "AUDCAD=X", "AUDCHF": "AUDCHF=X", "AUDJPY": "AUDJPY=X",
    "AUDNZD": "AUDNZD=X", "CADCHF": "CADCHF=X", "CADJPY": "CADJPY=X",
    "CHFJPY": "CHFJPY=X", "NZDCAD": "NZDCAD=X", "NZDCHF": "NZDCHF=X",
    "NZDJPY": "NZDJPY=X",
}


def _normalise_pair(pair: str) -> str:
    return pair.upper().replace("/", "").replace("-", "")


def _yf_ticker(pair: str) -> str:
    return _YF_MAP.get(_normalise_pair(pair), _normalise_pair(pair) + "=X")


def _pip_size(pair: str) -> float:
    p = _normalise_pair(pair)
    if "JPY" in p or "INR" in p:
        return 0.01
    return 0.0001


def _ema(s: pd.Series, n: int) -> pd.Series:
    return s.ewm(span=n, adjust=False).mean()


def _atr(df: pd.DataFrame, n: int = 14) -> pd.Series:
    hl = df["high"] - df["low"]
    hc = (df["high"] - df["close"].shift()).abs()
    lc = (df["low"]  - df["close"].shift()).abs()
    tr = pd.concat([hl, hc, lc], axis=1).max(axis=1)
    return tr.rolling(n).mean()


def _fetch_ohlcv(pair: str, days: int) -> Optional[pd.DataFrame]:
    ticker = _yf_ticker(pair)
    period = f"{min(days + 30, 730)}d"
    try:
        import yfinance as yf
        warnings.filterwarnings("ignore")
        df = yf.download(ticker, period=period, interval="1h", auto_adjust=True, progress=False)
        if df.empty:
            return None
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = [c[0].lower() for c in df.columns]
        else:
            df.columns = [c.lower() for c in df.columns]
        df["volume"] = df.get("volume", pd.Series(0, index=df.index))
        df = df[["open", "high", "low", "close", "volume"]].dropna(subset=["open", "close"])
        # Only keep requested days
        cutoff = pd.Timestamp.now(tz="UTC") - pd.Timedelta(days=days)
        if df.index.tz is None:
            df.index = df.index.tz_localize("UTC")
        df = df[df.index >= cutoff]
        return df
    except Exception as e:
        logger.error("Backtest yfinance fetch failed %s: %s", pair, e)
        return None


def _smc_signal_fast(df_slice: pd.DataFrame, direction_hint: Optional[str] = None) -> Optional[dict]:
    """
    Lightweight SMC check on a slice (last N candles).
    Returns dict with direction, entry, sl, tp1 or None.
    """
    if len(df_slice) < 50:
        return None
    close = df_slice["close"]
    price = float(close.iloc[-1])

    e9  = float(_ema(close, 9).iloc[-1])
    e15 = float(_ema(close, 15).iloc[-1])
    atr_val = float(_atr(df_slice).iloc[-1])
    if np.isnan(atr_val) or atr_val == 0:
        return None

    ema_bull = e9 > e15 and price > e15
    ema_bear = e9 < e15 and price < e15

    # Detect bullish FVG in last 30 candles
    tail = df_slice.tail(32)
    bull_fvg = False
    bear_fvg = False
    for i in range(2, len(tail)):
        c0, c2 = tail.iloc[i - 2], tail.iloc[i]
        if c0["high"] < c2["low"]:
            bull_fvg = True
        if c0["low"] > c2["high"]:
            bear_fvg = True

    # Detect liquidity sweep in last 3 candles
    swing_w = df_slice.iloc[-18:-3]
    s_high = float(swing_w["high"].max())
    s_low  = float(swing_w["low"].min())
    last3  = df_slice.tail(3)
    sell_sweep = any(
        r["low"] < s_low and r["close"] > s_low for _, r in last3.iterrows()
    )
    buy_sweep = any(
        r["high"] > s_high and r["close"] < s_high for _, r in last3.iterrows()
    )

    buy_score  = (30 if ema_bull else 0) + (35 if sell_sweep else 0) + (25 if bull_fvg else 0)
    sell_score = (30 if ema_bear else 0) + (35 if buy_sweep  else 0) + (25 if bear_fvg else 0)

    if buy_score >= 55 and buy_score >= sell_score:
        sl  = round(price - 1.5 * atr_val, 5)
        risk = abs(price - sl)
        return {"direction": "BUY",  "entry": price, "sl": sl,
                "tp1": round(price + risk, 5), "score": buy_score}
    if sell_score >= 55 and sell_score > buy_score:
        sl  = round(price + 1.5 * atr_val, 5)
        risk = abs(price - sl)
        return {"direction": "SELL", "entry": price, "sl": sl,
                "tp1": round(price - risk, 5), "score": sell_score}
    return None


def run_backtest(pair: str, days: int = 90) -> dict:
    """
    Walk-forward backtest of SMC strategy on 1H data.
    Returns full stats + trades list.
    """
    df = _fetch_ohlcv(pair, days)
    if df is None or len(df) < 60:
        return {"error": f"Not enough data for {pair}"}

    pip = _pip_size(pair)
    trades = []
    open_trade: Optional[dict] = None
    LOOKBACK = 50

    for i in range(LOOKBACK, len(df) - 1):
        current_bar = df.iloc[i]
        ts = str(df.index[i])

        # Check if open trade hit SL or TP1
        if open_trade:
            hi = float(current_bar["high"])
            lo = float(current_bar["low"])
            entry = open_trade["entry"]
            sl    = open_trade["sl"]
            tp1   = open_trade["tp1"]
            direct = open_trade["direction"]

            hit_sl  = (direct == "BUY"  and lo  <= sl)  or (direct == "SELL" and hi >= sl)
            hit_tp1 = (direct == "BUY"  and hi  >= tp1) or (direct == "SELL" and lo <= tp1)

            if hit_sl or hit_tp1:
                exit_price = tp1 if hit_tp1 else sl
                pnl_pips = (
                    (exit_price - entry) / pip if direct == "BUY"
                    else (entry - exit_price) / pip
                )
                rr = abs(pnl_pips) / max(abs(entry - sl) / pip, 0.001) if hit_tp1 else -1.0
                open_trade.update({
                    "exit_time":  ts,
                    "exit_price": round(exit_price, 5),
                    "result":     "WIN" if hit_tp1 else "LOSS",
                    "pnl_pips":   round(pnl_pips, 1),
                    "rr_achieved": round(rr, 2),
                })
                trades.append(open_trade)
                open_trade = None
            continue

        # Only try to enter if no open trade
        slice_ = df.iloc[max(0, i - LOOKBACK): i + 1]
        sig = _smc_signal_fast(slice_)
        if sig:
            open_trade = {
                "entry_time": ts,
                "direction":  sig["direction"],
                "entry":      sig["entry"],
                "sl":         sig["sl"],
                "tp1":        sig["tp1"],
            }

    # Any still-open trade at end → OPEN
    if open_trade:
        last_price = float(df["close"].iloc[-1])
        pnl_pips = (
            (last_price - open_trade["entry"]) / pip if open_trade["direction"] == "BUY"
            else (open_trade["entry"] - last_price) / pip
        )
        open_trade.update({
            "exit_time":   str(df.index[-1]),
            "exit_price":  round(last_price, 5),
            "result":      "OPEN",
            "pnl_pips":    round(pnl_pips, 1),
            "rr_achieved": 0.0,
        })
        trades.append(open_trade)

    if not trades:
        return {
            "pair": pair, "days": days, "total_trades": 0,
            "wins": 0, "losses": 0, "win_rate": 0,
            "avg_rr": 0, "total_pips": 0,
            "max_drawdown_pips": 0, "profit_factor": 0, "trades": [],
        }

    wins   = [t for t in trades if t["result"] == "WIN"]
    losses = [t for t in trades if t["result"] == "LOSS"]
    total  = len([t for t in trades if t["result"] != "OPEN"])

    total_pips = sum(t["pnl_pips"] for t in trades)
    win_pips   = sum(t["pnl_pips"] for t in wins)
    loss_pips  = abs(sum(t["pnl_pips"] for t in losses))

    # Max drawdown (running cumulative pips)
    cumulative = 0.0
    peak = 0.0
    max_dd = 0.0
    for t in trades:
        cumulative += t["pnl_pips"]
        if cumulative > peak:
            peak = cumulative
        dd = peak - cumulative
        if dd > max_dd:
            max_dd = dd

    result = {
        "pair":               pair,
        "days":               days,
        "total_trades":       len(trades),
        "wins":               len(wins),
        "losses":             len(losses),
        "win_rate":           round(len(wins) / max(total, 1) * 100, 1),
        "avg_rr":             round(sum(t["rr_achieved"] for t in wins) / max(len(wins), 1), 2),
        "total_pips":         round(total_pips, 1),
        "max_drawdown_pips":  round(max_dd, 1),
        "profit_factor":      round(win_pips / max(loss_pips, 0.001), 2),
        "trades":             trades[:200],
        "generated_at":       datetime.now(IST).isoformat(),
    }
    return result


def save_result(result: dict, pair: str, days: int) -> str:
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    filename = f"{_normalise_pair(pair)}_{days}d_{ts}.json"
    path = DATA_DIR / filename
    path.write_text(json.dumps(result, default=str, indent=2))
    return filename


def list_results() -> list[dict]:
    files = sorted(DATA_DIR.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
    out = []
    for f in files[:50]:
        try:
            data = json.loads(f.read_text())
            out.append({
                "filename":    f.name,
                "pair":        data.get("pair"),
                "days":        data.get("days"),
                "total_trades":data.get("total_trades"),
                "win_rate":    data.get("win_rate"),
                "total_pips":  data.get("total_pips"),
                "generated_at":data.get("generated_at"),
            })
        except Exception:
            pass
    return out


def get_result(filename: str) -> Optional[dict]:
    path = DATA_DIR / filename
    if not path.exists() or not path.is_file():
        return None
    try:
        return json.loads(path.read_text())
    except Exception:
        return None
