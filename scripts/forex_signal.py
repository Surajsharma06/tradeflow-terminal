#!/usr/bin/env python3
"""
Forex Signal Generator — AI-Powered
=====================================
Runs every 5 minutes, generates BUY/SELL signals
for 24 forex pairs using XGBoost model.

Usage:
  python3 forex_signal.py          # run once
  python3 forex_signal.py --loop   # run every 5 min
"""

import os, sys, json, pickle, warnings, time, argparse
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

warnings.filterwarnings("ignore")

import numpy as np
import pandas as pd
import yfinance as yf
import xgboost as xgb
from sklearn.preprocessing import RobustScaler

# ── Paths ──────────────────────────────────────────────────────────────────
BASE        = Path("/Users/surajbhadola/Downloads/Trading")
MODEL_PATH  = BASE / "models" / "forex_xgb_model.json"
SCALER_PATH = BASE / "models" / "forex_scaler.pkl"
SIG_DIR     = BASE / "data" / "signals"
SIG_DIR.mkdir(parents=True, exist_ok=True)
SIG_PATH    = SIG_DIR / "latest_signals.json"

# ── Pairs ──────────────────────────────────────────────────────────────────
PAIRS = {
    "EUR/USD": "EURUSD=X",  "GBP/USD": "GBPUSD=X",
    "USD/JPY": "USDJPY=X",  "USD/CHF": "USDCHF=X",
    "AUD/USD": "AUDUSD=X",  "USD/CAD": "USDCAD=X",
    "NZD/USD": "NZDUSD=X",  "EUR/GBP": "EURGBP=X",
    "EUR/JPY": "EURJPY=X",  "GBP/JPY": "GBPJPY=X",
    "AUD/CAD": "AUDCAD=X",  "AUD/JPY": "AUDJPY=X",
    "CAD/JPY": "CADJPY=X",  "EUR/CHF": "EURCHF=X",
    "GBP/CHF": "GBPCHF=X",  "NZD/JPY": "NZDJPY=X",
    "EUR/AUD": "EURAUD=X",  "GBP/AUD": "GBPAUD=X",
    "EUR/CAD": "EURCAD=X",  "USD/INR": "USDINR=X",
    "XAU/USD": "GC=F",      "XAG/USD": "SI=F",
    "BTC/USD": "BTC-USD",   "ETH/USD": "ETH-USD",
}

PIP_FACTOR = {
    "JPY": 100, "INR": 100, "MXN": 100, "ZAR": 100, "SGD": 10000,
    "XAU": 10,  "XAG": 100, "BTC": 1,   "ETH": 1,
}

SESSION_NAMES  = {0: "Asian 🌏", 1: "London 🇬🇧", 2: "London/NY 🔥", 3: "New York 🗽"}
SESSION_LABELS = {0: "Asian",   1: "London",     2: "London/NY",    3: "New York"}

FEATURES = [
    "atr_14", "atr_pct", "adx_14", "ema_align", "rsi_14",
    "macd_hist_dir", "bb_width", "session",
    "dist_prev_day_high", "dist_prev_day_low",
    "dist_prev_week_high", "dist_prev_week_low",
    "dist_round_number", "market_struct",
    "hour_utc", "day_of_week",
]

CONFIDENCE_MIN = 65   # minimum % to show signal
ADX_MIN        = 25
ATR_PCT_MIN    = 0.05

NEWS_TIMES_MIN = [8*60+30, 9*60+30, 13*60+30, 14*60+30, 15*60+30, 18*60]
NEWS_WINDOW    = 30

# ═══════════════════════════════════════════════════════════════════════════
# INDICATOR FUNCTIONS
# ═══════════════════════════════════════════════════════════════════════════

def ema(s, n):  return s.ewm(span=n, adjust=False).mean()

def atr_series(df, n=14):
    hl = df["high"] - df["low"]
    hc = (df["high"] - df["close"].shift()).abs()
    lc = (df["low"]  - df["close"].shift()).abs()
    tr = pd.concat([hl, hc, lc], axis=1).max(axis=1)
    return tr.ewm(span=n, adjust=False).mean()

def rsi_series(s, n=14):
    d  = s.diff()
    g  = d.clip(lower=0).ewm(span=n, adjust=False).mean()
    lo = (-d.clip(upper=0)).ewm(span=n, adjust=False).mean()
    return 100 - 100 / (1 + g / lo.replace(0, np.nan))

def adx_series(df, n=14):
    h, l, c = df["high"], df["low"], df["close"]
    tr = atr_series(df, 1)
    dm_p = h.diff().clip(lower=0);   dm_p[h.diff() < l.diff().abs()] = 0
    dm_m = (-l.diff()).clip(lower=0); dm_m[l.diff().abs() < h.diff()] = 0
    atr14 = tr.rolling(n).sum()
    di_p = 100 * dm_p.rolling(n).sum() / atr14.replace(0, np.nan)
    di_m = 100 * dm_m.rolling(n).sum() / atr14.replace(0, np.nan)
    dx   = 100 * (di_p - di_m).abs() / (di_p + di_m).replace(0, np.nan)
    return dx.ewm(span=n, adjust=False).mean()

def macd_hist_series(s, f=12, sl=26, sig=9):
    m = ema(s, f) - ema(s, sl)
    return np.sign(m - m.ewm(span=sig, adjust=False).mean()).astype("int8")

def bb_width_series(s, n=20):
    mid = s.rolling(n).mean(); std = s.rolling(n).std()
    return ((mid + 2*std) - (mid - 2*std)) / mid.replace(0, np.nan)

def get_session(ts):
    h = ts.hour
    if   7  <= h < 12: return 1
    elif 12 <= h < 16: return 2
    elif 16 <= h < 21: return 3
    else:              return 0

def is_news_risk(ts):
    m = ts.hour * 60 + ts.minute
    return any(abs(m - nt) <= NEWS_WINDOW for nt in NEWS_TIMES_MIN)

def pip_size(pair: str) -> float:
    for suffix, factor in PIP_FACTOR.items():
        if suffix in pair.replace("/", ""):
            return 1.0 / factor
    return 0.0001

# ═══════════════════════════════════════════════════════════════════════════
# STEP 1 — FETCH DATA
# ═══════════════════════════════════════════════════════════════════════════

def fetch_pair(ticker: str, n_candles: int = 200) -> Optional[pd.DataFrame]:
    try:
        df = yf.download(ticker, period="30d", interval="1h",
                         auto_adjust=True, progress=False)
        if df is None or df.empty:
            return None
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = [c[0].lower() for c in df.columns]
        else:
            df.columns = [c.lower() for c in df.columns]
        df.index = pd.to_datetime(df.index, utc=True)
        if "volume" not in df.columns: df["volume"] = 0
        df = df[["open","high","low","close","volume"]].dropna(subset=["open","close"])
        return df.tail(n_candles)
    except Exception as e:
        return None

# ═══════════════════════════════════════════════════════════════════════════
# STEP 2 — CALCULATE INDICATORS
# ═══════════════════════════════════════════════════════════════════════════

def calc_indicators(df: pd.DataFrame, pair: str) -> pd.DataFrame:
    c, h, l = df["close"], df["high"], df["low"]

    # EMAs
    e20  = ema(c, 20); e50 = ema(c, 50); e200 = ema(c, 200)
    df["ema_20"]  = e20;  df["ema_50"] = e50;  df["ema_200"] = e200
    df["ema_align"] = np.where((e20>e50)&(e50>e200), 1,
                      np.where((e20<e50)&(e50<e200),-1, 0)).astype("int8")

    # Volatility / momentum
    df["atr_14"]      = atr_series(df, 14)
    df["atr_pct"]     = (df["atr_14"] / c * 100)
    df["adx_14"]      = adx_series(df, 14)
    df["rsi_14"]      = rsi_series(c, 14)
    df["macd_hist_dir"] = macd_hist_series(c)
    df["bb_width"]    = bb_width_series(c, 20)

    # Prev day H/L
    dates = df.index.date
    day_h = df.groupby(dates)["high"].transform("max")
    day_l = df.groupby(dates)["low"].transform("min")
    df["prev_day_high"] = day_h.shift(1)
    df["prev_day_low"]  = day_l.shift(1)

    # Prev week H/L
    iso = df.index.isocalendar()
    wk  = (pd.Series(iso["year"].values, index=df.index).astype(str) + "_" +
           pd.Series(iso["week"].values, index=df.index).astype(str))
    wh  = df.groupby(wk.values)["high"].transform("max")
    wl  = df.groupby(wk.values)["low"].transform("min")
    df["prev_week_high"] = pd.Series(wh.values, index=df.index).shift(1)
    df["prev_week_low"]  = pd.Series(wl.values, index=df.index).shift(1)

    # Round number distance
    step = 0.01 if any(x in pair for x in ["JPY","INR","MXN","ZAR"]) else (
           50.0 if any(x in pair for x in ["BTC","XAU"]) else (
           0.5  if "XAG" in pair else 0.005))
    df["round_dist"] = (c % step).combine(step - c % step, min)

    # Market structure
    ph = h.rolling(5).max().shift(1); pl = l.rolling(5).min().shift(1)
    df["market_struct"] = np.where((h>ph)&(l>pl), 2,
                          np.where((h<ph)&(l>pl), 1,
                          np.where((h<ph)&(l<pl),-1,
                          np.where((h>ph)&(l<pl),-2, 0)))).astype("int8")

    # Session & News (per row)
    df["session"]   = [get_session(ts) for ts in df.index]
    df["news_risk"] = [is_news_risk(ts) for ts in df.index]

    # Time features
    df["hour_utc"]    = [ts.hour       for ts in df.index]
    df["day_of_week"] = [ts.dayofweek  for ts in df.index]

    # Distance features (in ATR units)
    atr = df["atr_14"].replace(0, np.nan)
    df["dist_prev_day_high"]  = (df["prev_day_high"]  - c) / atr
    df["dist_prev_day_low"]   = (c - df["prev_day_low"])   / atr
    df["dist_prev_week_high"] = (df["prev_week_high"] - c) / atr
    df["dist_prev_week_low"]  = (c - df["prev_week_low"])  / atr
    df["dist_round_number"]   = df["round_dist"]           / atr

    return df

# ═══════════════════════════════════════════════════════════════════════════
# MAIN SIGNAL GENERATOR
# ═══════════════════════════════════════════════════════════════════════════

def run_signals():
    now_utc = datetime.now(timezone.utc)
    ts_str  = now_utc.strftime("%Y-%m-%d %H:%M:%S UTC")
    current_session = get_session(now_utc)

    # ── Load model ────────────────────────────────────────────────────────
    if not MODEL_PATH.exists() or not SCALER_PATH.exists():
        print("  ✗ Model not found! Run train_model.py first.")
        sys.exit(1)

    model = xgb.XGBClassifier()
    model.load_model(str(MODEL_PATH))
    with open(SCALER_PATH, "rb") as f:
        scaler: RobustScaler = pickle.load(f)

    # ── Print header ──────────────────────────────────────────────────────
    print(f"\n{'═'*52}")
    print(f"  📡 FOREX SIGNAL GENERATOR — AI Powered")
    print(f"  🕐 {ts_str}")
    print(f"  📍 Session: {SESSION_NAMES.get(current_session, 'Unknown')}")
    print(f"{'═'*52}\n")

    all_signals = []
    hold_reasons = []

    for pair, ticker in PAIRS.items():
        # ── Fetch ─────────────────────────────────────────────────────────
        df = fetch_pair(ticker, n_candles=200)
        if df is None or len(df) < 50:
            hold_reasons.append(f"  ⚠  {pair:<12s} → No data")
            continue

        # ── Indicators ────────────────────────────────────────────────────
        try:
            df = calc_indicators(df, pair)
        except Exception as e:
            hold_reasons.append(f"  ⚠  {pair:<12s} → Indicator error: {e}")
            continue

        # Get latest row
        row = df.iloc[-1]
        price    = float(row["close"])
        atr_val  = float(row["atr_14"]) if not np.isnan(row["atr_14"]) else 0
        adx_val  = float(row["adx_14"]) if not np.isnan(row["adx_14"]) else 0
        atr_pct  = float(row["atr_pct"]) if not np.isnan(row["atr_pct"]) else 0
        session  = int(row["session"])
        news     = bool(row["news_risk"])
        ema_aln  = int(row["ema_align"])

        # ── Pre-filters ───────────────────────────────────────────────────
        if adx_val <= ADX_MIN:
            hold_reasons.append(f"  ❌ {pair:<12s} → HOLD (ADX low: {adx_val:.1f})")
            continue
        if session == 0:
            hold_reasons.append(f"  ❌ {pair:<12s} → HOLD (Asian session)")
            continue
        if news:
            hold_reasons.append(f"  ❌ {pair:<12s} → HOLD (News risk ±30min)")
            continue
        if atr_pct <= ATR_PCT_MIN:
            hold_reasons.append(f"  ❌ {pair:<12s} → HOLD (Low volatility: {atr_pct:.3f}%)")
            continue
        if ema_aln == 0:
            hold_reasons.append(f"  ❌ {pair:<12s} → HOLD (EMAs choppy)")
            continue

        # ── AI Prediction ─────────────────────────────────────────────────
        feat_row = pd.DataFrame([row[FEATURES]])
        feat_row = feat_row.replace([np.inf, -np.inf], np.nan).fillna(0)

        try:
            X_scaled = scaler.transform(feat_row[FEATURES])
            proba    = model.predict_proba(X_scaled)[0]   # [SELL, HOLD, BUY]
            pred_cls = int(np.argmax(proba))              # 0=SELL, 1=HOLD, 2=BUY
            confidence = int(round(proba[pred_cls] * 100))
        except Exception as e:
            hold_reasons.append(f"  ⚠  {pair:<12s} → Prediction error: {e}")
            continue

        # Map class back
        label_map = {0: "SELL", 1: "HOLD", 2: "BUY"}
        signal = label_map[pred_cls]

        if signal == "HOLD" or confidence < CONFIDENCE_MIN:
            hold_reasons.append(
                f"  ❌ {pair:<12s} → HOLD (confidence: {confidence}%)"
            )
            continue

        # ── Calculate Levels ──────────────────────────────────────────────
        pip = pip_size(pair)

        if signal == "BUY":
            sl  = round(price - 1.5 * atr_val, 6)
            tp1 = round(price + 2.0 * atr_val, 6)
            tp2 = round(price + 3.5 * atr_val, 6)
            tp3 = round(price + 5.0 * atr_val, 6)
            sl_pips  = round((price - sl)  / pip, 1)
            tp1_pips = round((tp1 - price) / pip, 1)
            tp2_pips = round((tp2 - price) / pip, 1)
            tp3_pips = round((tp3 - price) / pip, 1)
        else:  # SELL
            sl  = round(price + 1.5 * atr_val, 6)
            tp1 = round(price - 2.0 * atr_val, 6)
            tp2 = round(price - 3.5 * atr_val, 6)
            tp3 = round(price - 5.0 * atr_val, 6)
            sl_pips  = round((sl - price)   / pip, 1)
            tp1_pips = round((price - tp1)  / pip, 1)
            tp2_pips = round((price - tp2)  / pip, 1)
            tp3_pips = round((price - tp3)  / pip, 1)

        rr_val  = round(tp1_pips / sl_pips, 1) if sl_pips > 0 else 0
        rr_str  = f"1:{rr_val}"
        arrow   = "▲" if signal == "BUY" else "▼"
        color   = "BUY ▲" if signal == "BUY" else "SELL ▼"

        # ── Print signal ──────────────────────────────────────────────────
        print(f"  ✅ {pair:<10s} → {color}")
        print(f"     Confidence: {confidence}%")
        print(f"     Entry:  {price:.5f}")
        if signal == "BUY":
            print(f"     SL:     {sl:.5f}  (-{sl_pips} pips)")
            print(f"     TP1:    {tp1:.5f}  (+{tp1_pips} pips)")
            print(f"     TP2:    {tp2:.5f}  (+{tp2_pips} pips)")
            print(f"     TP3:    {tp3:.5f}  (+{tp3_pips} pips)")
        else:
            print(f"     SL:     {sl:.5f}  (+{sl_pips} pips)")
            print(f"     TP1:    {tp1:.5f}  (-{tp1_pips} pips)")
            print(f"     TP2:    {tp2:.5f}  (-{tp2_pips} pips)")
            print(f"     TP3:    {tp3:.5f}  (-{tp3_pips} pips)")
        print(f"     R:R  → {rr_str}")
        print(f"     ADX: {adx_val:.1f} ✅  |  Session: {SESSION_LABELS[session]}")
        print()

        all_signals.append({
            "pair":           pair,
            "session":        SESSION_LABELS[session],
            "signal":         signal,
            "confidence":     confidence,
            "entry":          round(price, 6),
            "sl":             sl,
            "tp1":            tp1,
            "tp2":            tp2,
            "tp3":            tp3,
            "sl_pips":        sl_pips,
            "tp1_pips":       tp1_pips,
            "rr":             rr_str,
            "adx":            round(adx_val, 2),
            "atr":            round(atr_val, 6),
            "atr_pct":        round(atr_pct, 4),
            "ema_align":      ema_aln,
            "filters_passed": True,
        })

    # ── Print HOLD reasons ────────────────────────────────────────────────
    if hold_reasons:
        print(f"  {'─'*48}")
        for r in hold_reasons:
            print(r)

    # ── Summary ───────────────────────────────────────────────────────────
    n_buy  = sum(1 for s in all_signals if s["signal"] == "BUY")
    n_sell = sum(1 for s in all_signals if s["signal"] == "SELL")
    print(f"\n{'═'*52}")
    print(f"  📊 Signals: {len(all_signals)} total "
          f"(BUY={n_buy}  SELL={n_sell}  HOLD={len(hold_reasons)})")
    print(f"  💾 Saved → {SIG_PATH}")
    print(f"{'═'*52}\n")

    # ── Save JSON ─────────────────────────────────────────────────────────
    out = {
        "timestamp":  ts_str,
        "session":    SESSION_LABELS.get(current_session, "Unknown"),
        "pair_count": len(PAIRS),
        "signals":    all_signals,
    }
    with open(SIG_PATH, "w") as f:
        json.dump(out, f, indent=2)

    return all_signals


# ═══════════════════════════════════════════════════════════════════════════
# ENTRY POINT
# ═══════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Forex Signal Generator")
    parser.add_argument("--loop",     action="store_true", help="Run every 5 min")
    parser.add_argument("--interval", type=int, default=300, help="Interval seconds (default 300)")
    args = parser.parse_args()

    if args.loop:
        print(f"  🔁 Auto-loop mode: running every {args.interval}s")
        print(f"     Press Ctrl+C to stop\n")
        while True:
            try:
                run_signals()
                print(f"  ⏱  Next run in {args.interval}s...")
                time.sleep(args.interval)
            except KeyboardInterrupt:
                print("\n  ✅ Stopped by user.")
                break
            except Exception as e:
                print(f"  ✗ Error: {e} — retrying in 60s")
                time.sleep(60)
    else:
        run_signals()
