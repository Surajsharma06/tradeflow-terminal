"""
Historical Forex Data Downloader — yfinance
============================================
Downloads OHLCV data for all major/minor/exotic pairs,
metals, and crypto across 3 timeframes.
"""

import os
import warnings
warnings.filterwarnings("ignore")

import pandas as pd
import yfinance as yf
from datetime import datetime, timedelta

# ── Output directories ─────────────────────────────────────────────────────
BASE = "/Users/surajbhadola/Downloads/Trading/data/forex"
DIRS = {
    "1d":  os.path.join(BASE, "daily"),
    "1h":  os.path.join(BASE, "hourly"),
    "15m": os.path.join(BASE, "15min"),
}
for d in DIRS.values():
    os.makedirs(d, exist_ok=True)

# ── All pairs ──────────────────────────────────────────────────────────────
PAIRS = {
    # Major
    "EURUSD=X":  "EURUSD",
    "GBPUSD=X":  "GBPUSD",
    "USDJPY=X":  "USDJPY",
    "USDCHF=X":  "USDCHF",
    "AUDUSD=X":  "AUDUSD",
    "USDCAD=X":  "USDCAD",
    "NZDUSD=X":  "NZDUSD",
    # Minor
    "EURGBP=X":  "EURGBP",
    "EURJPY=X":  "EURJPY",
    "GBPJPY=X":  "GBPJPY",
    "AUDCAD=X":  "AUDCAD",
    "AUDJPY=X":  "AUDJPY",
    "CADJPY=X":  "CADJPY",
    "EURCHF=X":  "EURCHF",
    "GBPCHF=X":  "GBPCHF",
    "NZDJPY=X":  "NZDJPY",
    "EURAUD=X":  "EURAUD",
    "GBPAUD=X":  "GBPAUD",
    "EURCAD=X":  "EURCAD",
    # Exotic
    "USDINR=X":  "USDINR",
    "USDSGD=X":  "USDSGD",
    "USDMXN=X":  "USDMXN",
    "USDZAR=X":  "USDZAR",
    # Metals — correct tickers (GC=F Gold Futures, SI=F Silver Futures)
    "GC=F":      "XAUUSD",
    "SI=F":      "XAGUSD",
    # Crypto
    "BTC-USD":   "BTCUSD",
    "ETH-USD":   "ETHUSD",
}

# ── Download config ────────────────────────────────────────────────────────
# Use period= (not start=) for intraday — yfinance handles it more reliably
TASKS = [
    # (interval, folder_key, yfinance_kwargs)
    ("1d",  "1d",  {"period": "max"}),
    ("1h",  "1h",  {"period": "720d"}),   # ~2 years, yfinance max for 1h
    ("15m", "15m", {"period": "59d"}),    # 59 days, yfinance max for 15m
]


# ── Results table ──────────────────────────────────────────────────────────
results = []
errors  = []

print(f"\n{'='*70}")
print(f"  Forex Historical Data Downloader")
print(f"  Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
print(f"  Pairs: {len(PAIRS)} | Timeframes: 3")
print(f"{'='*70}\n")

for ticker, name in PAIRS.items():
    for interval, folder_key, kwargs in TASKS:
        out_dir  = DIRS[folder_key]
        filename = f"{name}_{interval.replace('m','m')}.csv"
        filepath = os.path.join(out_dir, filename)

        try:
            df = yf.download(
                ticker,
                interval=interval,
                auto_adjust=True,
                progress=False,
                **kwargs
            )

            # Flatten MultiIndex if present
            if isinstance(df.columns, pd.MultiIndex):
                df.columns = [c[0] for c in df.columns]

            df.columns = [c.lower() for c in df.columns]

            if df.empty:
                msg = f"  ⚠  {name:10s} {interval:4s} → EMPTY (no data)"
                print(msg)
                errors.append((ticker, interval, "empty"))
                continue

            # Keep only OHLCV
            keep = [c for c in ["open", "high", "low", "close", "volume"] if c in df.columns]
            df   = df[keep].dropna(subset=["open", "close"])

            # Save CSV
            df.to_csv(filepath)

            rows     = len(df)
            date_min = df.index[0].strftime("%Y-%m-%d") if hasattr(df.index[0], 'strftime') else str(df.index[0])[:10]
            date_max = df.index[-1].strftime("%Y-%m-%d") if hasattr(df.index[-1], 'strftime') else str(df.index[-1])[:10]

            line = f"  ✓  {name:10s} {interval:4s} → {rows:6,d} rows  [{date_min} → {date_max}]"
            print(line)
            results.append({
                "pair": name, "interval": interval,
                "rows": rows, "from": date_min, "to": date_max,
                "file": filepath
            })

        except Exception as e:
            msg = f"  ✗  {name:10s} {interval:4s} → ERROR: {e}"
            print(msg)
            errors.append((ticker, interval, str(e)))

# ── Summary ────────────────────────────────────────────────────────────────
print(f"\n{'='*70}")
print(f"  SUMMARY")
print(f"{'='*70}")

df_res = pd.DataFrame(results)
if not df_res.empty:
    print(f"\n  Total files saved : {len(results)}")
    print(f"  Total errors      : {len(errors)}")
    print(f"\n  By timeframe:")
    for tf, grp in df_res.groupby("interval"):
        total_rows = grp["rows"].sum()
        print(f"    {tf:4s}  → {len(grp):2d} files  |  {total_rows:,d} total rows")

    print(f"\n  Largest datasets (by rows):")
    top = df_res.nlargest(5, "rows")[["pair", "interval", "rows", "from", "to"]]
    print(top.to_string(index=False))

if errors:
    print(f"\n  Failed downloads ({len(errors)}):")
    for t, i, e in errors:
        print(f"    {t} {i}: {e}")

print(f"\n  Saved to: {BASE}")
print(f"  Finished: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
print(f"{'='*70}\n")
