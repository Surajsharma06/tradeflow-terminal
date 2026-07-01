"""
Forex Indicator Processor
=========================
Reads all CSV files from /data/forex/{daily,hourly,15min}/
Calculates forex-relevant indicators for each pair & timeframe.
Saves processed files to /data/forex/processed/
"""

import os
import warnings
warnings.filterwarnings("ignore")

import numpy as np
import pandas as pd
from pathlib import Path
from datetime import time as dtime

# ── Paths ──────────────────────────────────────────────────────────────────
BASE        = Path("/Users/surajbhadola/Downloads/Trading/data/forex")
OUT_DIR     = BASE / "processed"
OUT_DIR.mkdir(parents=True, exist_ok=True)

SOURCE_DIRS = {
    "1d":  BASE / "daily",
    "1h":  BASE / "hourly",
    "15m": BASE / "15min",
}

# ── News risk times (UTC hour, minute) ────────────────────────────────────
NEWS_TIMES_UTC = [
    dtime(8, 30), dtime(9, 30), dtime(13, 30),
    dtime(14, 30), dtime(15, 30), dtime(18, 0),
]
NEWS_WINDOW_MIN = 30   # minutes before/after

# ─────────────────────────────────────────────────────────────────────────
# INDICATOR FUNCTIONS
# ─────────────────────────────────────────────────────────────────────────

def ema(s: pd.Series, n: int) -> pd.Series:
    return s.ewm(span=n, adjust=False).mean()


def atr(df: pd.DataFrame, n: int = 14) -> pd.Series:
    hl  = df["high"] - df["low"]
    hc  = (df["high"] - df["close"].shift()).abs()
    lc  = (df["low"]  - df["close"].shift()).abs()
    tr  = pd.concat([hl, hc, lc], axis=1).max(axis=1)
    return tr.ewm(span=n, adjust=False).mean()


def rsi(s: pd.Series, n: int = 14) -> pd.Series:
    delta = s.diff()
    gain  = delta.clip(lower=0).ewm(span=n, adjust=False).mean()
    loss  = (-delta.clip(upper=0)).ewm(span=n, adjust=False).mean()
    rs    = gain / loss.replace(0, np.nan)
    return 100 - (100 / (1 + rs))


def adx(df: pd.DataFrame, n: int = 14) -> pd.Series:
    """Average Directional Index."""
    high, low, close = df["high"], df["low"], df["close"]
    tr  = atr(df, 1)   # single-period TR for smoothing
    dm_plus  = (high.diff()).clip(lower=0)
    dm_minus = (-low.diff()).clip(lower=0)
    # Zero out where opposite is larger
    cond = dm_plus < dm_minus
    dm_plus[cond]  = 0
    cond2 = dm_minus < dm_plus
    dm_minus[cond2] = 0

    atr14    = tr.rolling(n).sum()
    di_plus  = 100 * dm_plus.rolling(n).sum()  / atr14.replace(0, np.nan)
    di_minus = 100 * dm_minus.rolling(n).sum() / atr14.replace(0, np.nan)
    dx       = (100 * (di_plus - di_minus).abs() / (di_plus + di_minus).replace(0, np.nan))
    return dx.ewm(span=n, adjust=False).mean()


def macd_hist(s: pd.Series, fast=12, slow=26, signal=9) -> pd.Series:
    m = ema(s, fast) - ema(s, slow)
    return m - m.ewm(span=signal, adjust=False).mean()


def bb_width(s: pd.Series, n: int = 20) -> pd.Series:
    mid  = s.rolling(n).mean()
    std  = s.rolling(n).std()
    return ((mid + 2*std) - (mid - 2*std)) / mid.replace(0, np.nan)


def round_number_distance(price: pd.Series, step: float = 0.005) -> pd.Series:
    """Distance from nearest round number (e.g. 0.005 = 50 pips for majors)."""
    return (price % step).combine(step - price % step, min)


def market_structure(high: pd.Series, low: pd.Series,
                     lookback: int = 5) -> pd.Series:
    """
    Returns: 2=HH, 1=HL, -1=LH, -2=LL, 0=undefined
    Compares current high/low to previous swing high/low.
    """
    ph = high.rolling(lookback).max().shift(1)
    pl = low.rolling(lookback).min().shift(1)
    cond_hh = (high > ph) & (low > pl)
    cond_hl = (high < ph) & (low > pl)
    cond_lh = (high < ph) & (low < pl)
    cond_ll = (high > ph) & (low < pl)
    out = pd.Series(0, index=high.index, dtype="int8")
    out[cond_hh] = 2
    out[cond_hl] = 1
    out[cond_lh] = -1
    out[cond_ll] = -2
    return out


def prev_day_hl(df: pd.DataFrame, tf: str) -> tuple[pd.Series, pd.Series]:
    """Previous Day High/Low (meaningful for 1h and 15m)."""
    if tf == "1d":
        return df["high"].shift(1), df["low"].shift(1)
    day_group = df.groupby(df.index.date)
    daily_h   = day_group["high"].transform("max").shift(1)
    daily_l   = day_group["low"].transform("min").shift(1)
    return daily_h, daily_l


def prev_week_hl(df: pd.DataFrame) -> tuple[pd.Series, pd.Series]:
    """Previous Week High/Low."""
    # Use isocalendar week as string key to avoid tuple index issues
    iso = df.index.isocalendar()
    week_key = iso["year"].astype(str) + "_" + iso["week"].astype(str)
    week_key.index = df.index
    df["_wk"] = week_key.values
    weekly_h = df.groupby("_wk")["high"].transform("max")
    weekly_l = df.groupby("_wk")["low"].transform("min")
    df.drop(columns=["_wk"], inplace=True)
    return weekly_h.shift(1), weekly_l.shift(1)


def session_label(index: pd.DatetimeIndex) -> pd.Series:
    """
    0 = Asian / Dead Zone
    1 = London
    2 = London+NY Overlap
    3 = NY
    """
    # Use .hour on each element to handle tz-aware index safely
    hours = np.array([ts.hour for ts in index], dtype="int8")
    labels = np.zeros(len(hours), dtype="int8")
    labels[(hours >= 7)  & (hours < 12)] = 1
    labels[(hours >= 12) & (hours < 16)] = 2
    labels[(hours >= 16) & (hours < 21)] = 3
    return pd.Series(labels, index=index, name="session")


def news_risk_flag(index: pd.DatetimeIndex) -> pd.Series:
    """True if within 30 min of a major news release time (UTC)."""
    # Convert to minutes-of-day safely for tz-aware index
    row_minutes = np.array([ts.hour * 60 + ts.minute for ts in index], dtype="int32")
    flags = np.zeros(len(index), dtype=bool)
    for nt in NEWS_TIMES_UTC:
        news_minutes = nt.hour * 60 + nt.minute
        diff = np.abs(row_minutes - news_minutes)
        flags |= (diff <= NEWS_WINDOW_MIN)
    return pd.Series(flags, index=index, name="news_risk")


# ─────────────────────────────────────────────────────────────────────────
# MAIN PROCESSOR
# ─────────────────────────────────────────────────────────────────────────

def process_file(csv_path: Path, tf: str) -> tuple[str, int, str]:
    """
    Read one CSV, compute all indicators, save processed CSV.
    Returns (filename, row_count, status)
    """
    try:
        df = pd.read_csv(csv_path, index_col=0, parse_dates=True)
        df.index = pd.to_datetime(df.index, utc=True)
        df.index.name = "datetime"

        # Lowercase columns
        df.columns = [c.lower() for c in df.columns]
        needed = ["open", "high", "low", "close"]
        if not all(c in df.columns for c in needed):
            return (csv_path.name, 0, "SKIP — missing OHLC columns")

        df = df[["open","high","low","close"] +
                (["volume"] if "volume" in df.columns else [])].copy()
        df.dropna(subset=["open","high","low","close"], inplace=True)

        if len(df) < 30:
            return (csv_path.name, 0, "SKIP — too few rows")

        c = df["close"]
        h = df["high"]
        l = df["low"]

        # ── Trend ────────────────────────────────────────────────────────
        df["ema_20"]  = ema(c, 20).round(6)
        df["ema_50"]  = ema(c, 50).round(6)
        df["ema_200"] = ema(c, 200).round(6)

        e20 = df["ema_20"]
        e50 = df["ema_50"]
        e200= df["ema_200"]

        # EMA alignment: +1 bullish, -1 bearish, 0 mixed
        df["ema_align"] = np.where(
            (e20 > e50) & (e50 > e200), 1,
            np.where((e20 < e50) & (e50 < e200), -1, 0)
        ).astype("int8")

        df["adx_14"] = adx(df, 14).round(2)

        # ── Volatility ───────────────────────────────────────────────────
        df["atr_14"]    = atr(df, 14).round(6)
        df["atr_pct"]   = (df["atr_14"] / c * 100).round(4)
        df["bb_width"]  = bb_width(c, 20).round(6)

        # ── Momentum ─────────────────────────────────────────────────────
        rsi14           = rsi(c, 14).round(2)
        df["rsi_14"]    = rsi14
        # Extreme RSI flag: True if <25 or >75
        df["rsi_extreme"] = ((rsi14 < 25) | (rsi14 > 75))

        mh              = macd_hist(c)
        df["macd_hist_dir"] = np.sign(mh).astype("int8")   # +1/-1/0

        # ── Price Action ─────────────────────────────────────────────────
        # Previous Day H/L
        pdh, pdl            = prev_day_hl(df, tf)
        df["prev_day_high"] = pdh.round(6)
        df["prev_day_low"]  = pdl.round(6)

        # Previous Week H/L
        pwh, pwl             = prev_week_hl(df)
        df["prev_week_high"] = pwh.round(6)
        df["prev_week_low"]  = pwl.round(6)

        # Round number distance (pip step per pair from filename)
        name = csv_path.stem   # e.g. EURUSD_1h
        pair = name.split("_")[0]
        step = 0.01 if ("JPY" in pair or "INR" in pair or "MXN" in pair or
                        "ZAR" in pair or "SGD" in pair) else 0.005
        # For Gold/Silver/Crypto use larger steps
        if pair in ("XAUUSD", "BTCUSD", "ETHUSD"):
            step = 50.0
        elif pair == "XAGUSD":
            step = 0.5

        df["round_dist"] = round_number_distance(c, step).round(6)

        # Market structure
        lb = 3 if tf == "15m" else (5 if tf == "1h" else 5)
        ms = market_structure(h, l, lb)
        df["market_struct"] = ms  # 2=HH, 1=HL, -1=LH, -2=LL, 0=undefined
        df["market_struct_label"] = ms.map(
            {2:"HH", 1:"HL", -1:"LH", -2:"LL", 0:"—"}
        )

        # ── Session & News (only meaningful for intraday) ─────────────────
        if tf in ("1h", "15m"):
            df["session"]    = session_label(df.index).values
            df["news_risk"]  = news_risk_flag(df.index).values
        else:
            df["session"]    = -1   # N/A for daily
            df["news_risk"]  = False

        # ── Save ──────────────────────────────────────────────────────────
        out_name = f"{pair}_{tf}_processed.csv"
        out_path = OUT_DIR / out_name
        df.to_csv(out_path)

        return (out_name, len(df), "OK")

    except Exception as e:
        return (csv_path.name, 0, f"ERROR — {e}")


# ─────────────────────────────────────────────────────────────────────────
# RUN ALL FILES
# ─────────────────────────────────────────────────────────────────────────

print(f"\n{'='*72}")
print(f"  Forex Indicator Processor")
print(f"  Output: {OUT_DIR}")
print(f"{'='*72}\n")

results  = []
total_ok = 0
total_err= 0

for tf, src_dir in SOURCE_DIRS.items():
    if not src_dir.exists():
        print(f"  ⚠  Directory not found: {src_dir}")
        continue

    csv_files = sorted(src_dir.glob("*.csv"))
    if not csv_files:
        print(f"  ⚠  No CSV files in {src_dir}")
        continue

    print(f"  ── Timeframe: {tf.upper()} ({len(csv_files)} files) ──")

    for csv_path in csv_files:
        fname, rows, status = process_file(csv_path, tf)
        icon = "✓" if status == "OK" else "⚠" if "SKIP" in status else "✗"
        print(f"  {icon}  {fname:30s} → {rows:7,d} rows  [{status}]")
        results.append({"file": fname, "tf": tf, "rows": rows, "status": status})
        if status == "OK":
            total_ok += 1
        else:
            total_err += 1

    print()

# ── Summary ────────────────────────────────────────────────────────────────
df_res = pd.DataFrame(results)
ok_res = df_res[df_res["status"] == "OK"]

print(f"{'='*72}")
print(f"  FINAL SUMMARY")
print(f"{'='*72}")
print(f"  ✓ Processed OK : {total_ok}")
print(f"  ✗ Errors/Skips : {total_err}")
print(f"  Total rows     : {ok_res['rows'].sum():,}")
print()

if not ok_res.empty:
    print(f"  By timeframe:")
    for tf, grp in ok_res.groupby("tf"):
        print(f"    {tf:4s} → {len(grp):2d} files  |  {grp['rows'].sum():>10,d} rows")

    print(f"\n  Indicators added per file:")
    cols_added = [
        "ema_20", "ema_50", "ema_200", "ema_align",
        "adx_14", "atr_14", "atr_pct", "bb_width",
        "rsi_14", "rsi_extreme", "macd_hist_dir",
        "prev_day_high", "prev_day_low",
        "prev_week_high", "prev_week_low",
        "round_dist", "market_struct", "market_struct_label",
        "session", "news_risk",
    ]
    for i, c in enumerate(cols_added, 1):
        print(f"    {i:2d}. {c}")

print(f"\n  Saved to: {OUT_DIR}")
print(f"{'='*72}\n")
