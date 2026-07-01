#!/usr/bin/env python3
"""
Trading Bot Accuracy Analyzer v2
==================================
3 improvements implemented:
  1. Spread-aware target    — sirf profitable signals count honge
  2. Market session features — London/NY overlap identify karo
  3. High-ADX filter         — sideways market mein trade mat karo

Run:
    cd /Users/surajbhadola/Desktop/Trading
    python3 scripts/analyze_accuracy.py
"""

import sys, os, json, warnings
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))
warnings.filterwarnings("ignore")

import numpy as np
import pandas as pd
from datetime import datetime

# ─────────────────────────────────────────────────────────────────────────────
# CONFIG
# ─────────────────────────────────────────────────────────────────────────────

PAIRS    = ["EUR/USD", "GBP/USD", "USD/JPY", "USD/CAD", "AUD/USD"]
INTERVAL = "1h"
PERIOD   = "180d"
N_SPLITS = 5
MIN_CONF = 0.62      # raised from 0.60
ADX_MIN  = 25        # [STEP 3] only trade when ADX > this

# [STEP 1] Spread per pair (in price units, typical broker spread)
SPREAD = {
    "EUR/USD": 0.00012,
    "GBP/USD": 0.00018,
    "USD/JPY": 0.018,
    "USD/CAD": 0.00018,
    "AUD/USD": 0.00016,
}
SPREAD_MULTIPLIER = 2.0   # need to profit at least 2x spread to count as signal

# ─────────────────────────────────────────────────────────────────────────────
# DATA FETCH
# ─────────────────────────────────────────────────────────────────────────────

YF_MAP = {
    "EUR/USD": "EURUSD=X", "GBP/USD": "GBPUSD=X",
    "AUD/USD": "AUDUSD=X", "USD/JPY": "JPY=X",
    "USD/CAD": "CAD=X",
}

def fetch_data(pair: str) -> pd.DataFrame:
    print(f"  Fetching {pair}...", end=" ", flush=True)

    # Try Twelve Data first (real-time, no delay)
    try:
        from app.infrastructure.data_providers.unified_provider import UnifiedProvider
        df = UnifiedProvider().get_ohlcv(pair, period=PERIOD, interval=INTERVAL)
        if not df.empty and df["close"].std() > 1e-6:
            print(f"✓ {len(df)} candles [Twelve Data]")
            return df
    except Exception:
        pass

    # yfinance fallback
    try:
        import yfinance as yf
        ticker = YF_MAP.get(pair, pair.replace("/", "") + "=X")
        df = yf.download(ticker, period=PERIOD, interval=INTERVAL,
                         auto_adjust=True, progress=False)
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = [c[0].lower() for c in df.columns]
        else:
            df.columns = [c.lower() for c in df.columns]
        df["volume"] = df.get("volume", pd.Series(0, index=df.index)).fillna(0)
        df = df[["open","high","low","close","volume"]].dropna(subset=["close"])
        if not df.empty:
            print(f"✓ {len(df)} candles [yfinance]")
            return df
    except Exception as e:
        pass

    print("✗ FAILED")
    return pd.DataFrame()

# ─────────────────────────────────────────────────────────────────────────────
# STEP 2 — SESSION FEATURES
# ─────────────────────────────────────────────────────────────────────────────

def add_session_features(df: pd.DataFrame) -> pd.DataFrame:
    """
    Forex trades 24h/5 days. Different sessions have very different volatility.
    London-NY overlap (13:00-16:00 UTC) is the most liquid and predictable.
    """
    idx = df.index
    if idx.tz is None:
        idx = idx.tz_localize("UTC")
    else:
        idx = idx.tz_convert("UTC")

    hour = idx.hour

    # Session flags (UTC times)
    df["sess_tokyo"]   = ((hour >= 0)  & (hour < 9)).astype(int)
    df["sess_london"]  = ((hour >= 7)  & (hour < 16)).astype(int)
    df["sess_ny"]      = ((hour >= 13) & (hour < 22)).astype(int)
    df["sess_overlap"] = ((hour >= 13) & (hour < 16)).astype(int)   # BEST TIME
    df["sess_dead"]    = ((hour >= 22) | (hour < 0)).astype(int)    # avoid this

    # Day of week (0=Mon, 4=Fri) — Monday open and Friday close are noisy
    dow = idx.dayofweek
    df["dow_monday"]  = (dow == 0).astype(int)
    df["dow_friday"]  = (dow == 4).astype(int)
    df["dow_midweek"] = ((dow >= 1) & (dow <= 3)).astype(int)       # best days

    return df

# ─────────────────────────────────────────────────────────────────────────────
# FEATURE BUILDER
# ─────────────────────────────────────────────────────────────────────────────

def build_features(df: pd.DataFrame, pair: str) -> pd.DataFrame:
    d = df.copy()
    c = d["close"]
    spread = SPREAD.get(pair, 0.00015)

    # ── Returns ──────────────────────────────────────────────────────────────
    d["ret_3"]  = c.pct_change(3)
    d["ret_12"] = c.pct_change(12)

    # ── RSI ──────────────────────────────────────────────────────────────────
    delta = c.diff()
    gain  = delta.clip(lower=0).rolling(14).mean()
    loss  = (-delta.clip(upper=0)).rolling(14).mean()
    d["rsi"] = 100 - (100 / (1 + gain / (loss + 1e-9)))

    # ── MACD ─────────────────────────────────────────────────────────────────
    ema12          = c.ewm(span=12, adjust=False).mean()
    ema26          = c.ewm(span=26, adjust=False).mean()
    d["macd"]      = ema12 - ema26
    d["macd_sig"]  = d["macd"].ewm(span=9, adjust=False).mean()
    d["macd_hist"] = d["macd"] - d["macd_sig"]

    # ── ATR / Volatility ─────────────────────────────────────────────────────
    hl             = df["high"] - df["low"]
    hc             = (df["high"] - c.shift()).abs()
    lc             = (df["low"]  - c.shift()).abs()
    tr             = pd.concat([hl, hc, lc], axis=1).max(axis=1)
    atr            = tr.rolling(14).mean()
    d["atr_pct"]   = atr / (c + 1e-9)
    d["vol_5"]     = c.pct_change().rolling(5).std()
    d["vol_20"]    = c.pct_change().rolling(20).std()

    # ── ADX ──────────────────────────────────────────────────────────────────
    plus_dm   = (df["high"] - df["high"].shift()).clip(lower=0)
    minus_dm  = (df["low"].shift() - df["low"]).clip(lower=0)
    plus_dm   = plus_dm.where(plus_dm > minus_dm, 0)
    minus_dm  = minus_dm.where(minus_dm > plus_dm, 0)
    atr_s     = tr.rolling(14).mean()
    plus_di   = 100 * (plus_dm.rolling(14).mean() / (atr_s + 1e-9))
    minus_di  = 100 * (minus_dm.rolling(14).mean() / (atr_s + 1e-9))
    dx        = 100 * (plus_di - minus_di).abs() / (plus_di + minus_di + 1e-9)
    d["adx"]      = dx.rolling(14).mean()
    d["plus_di"]  = plus_di
    d["minus_di"] = minus_di

    # ── EMA distances ────────────────────────────────────────────────────────
    for p in [9, 21, 50, 200]:
        ema_val        = c.ewm(span=p, adjust=False).mean()
        d[f"dist_ema{p}"] = (c - ema_val) / (ema_val + 1e-9)

    # ── Price position ───────────────────────────────────────────────────────
    d["pp_20"] = (c - df["low"].rolling(20).min()) / \
                 (df["high"].rolling(20).max() - df["low"].rolling(20).min() + 1e-9)

    # ── STEP 2: Session features ─────────────────────────────────────────────
    d = add_session_features(d)

    # ── STEP 1: Spread-aware target ──────────────────────────────────────────
    # OLD: target = price goes up in 3 bars (useless — spread kha jaata tha)
    # NEW: target = price moves UP by at least 2x spread (profitable after cost)
    fwd_return       = c.shift(-3) - c
    min_profit       = spread * SPREAD_MULTIPLIER
    d["target"]      = np.where(fwd_return >  min_profit, 1,    # profitable BUY
                        np.where(fwd_return < -min_profit, 0,   # profitable SELL
                        np.nan))                                  # not worth trading
    # Drop the "not worth it" middle zone (HOLD)
    d = d.dropna(subset=["target"])
    d["target"] = d["target"].astype(int)

    return d.dropna()


FEATURE_COLS = [
    "ret_3", "ret_12",
    "rsi", "macd", "macd_sig", "macd_hist",
    "atr_pct", "vol_5", "vol_20",
    "adx", "plus_di", "minus_di",
    "dist_ema9", "dist_ema21", "dist_ema50", "dist_ema200",
    "pp_20",
    # STEP 2: session features
    "sess_tokyo", "sess_london", "sess_ny", "sess_overlap", "sess_dead",
    "dow_monday", "dow_friday", "dow_midweek",
]

# ─────────────────────────────────────────────────────────────────────────────
# FEATURE IMPORTANCE
# ─────────────────────────────────────────────────────────────────────────────

def run_feature_importance(df_feat: pd.DataFrame) -> list[dict]:
    import xgboost as xgb
    from sklearn.model_selection import train_test_split

    X = df_feat[FEATURE_COLS]
    y = df_feat["target"]
    X_tr, X_te, y_tr, y_te = train_test_split(X, y, test_size=0.2, shuffle=False)

    model = xgb.XGBClassifier(
        n_estimators=300, max_depth=4, learning_rate=0.05,
        subsample=0.8, colsample_bytree=0.8,
        eval_metric="logloss", random_state=42, n_jobs=-1,
    )
    model.fit(X_tr, y_tr, eval_set=[(X_te, y_te)], verbose=False)

    booster = model.get_booster()
    scores  = booster.get_score(importance_type="gain")
    total   = sum(scores.values()) or 1
    return sorted(
        [{"feature": k, "importance_pct": round(v/total*100, 2)} for k,v in scores.items()],
        key=lambda x: x["importance_pct"], reverse=True
    )

# ─────────────────────────────────────────────────────────────────────────────
# WALK-FORWARD WITH ADX FILTER
# ─────────────────────────────────────────────────────────────────────────────

def walk_forward(df_feat: pd.DataFrame, pair: str) -> dict:
    import xgboost as xgb
    from sklearn.metrics import accuracy_score, precision_score

    # STEP 3: Only keep rows where market is trending (ADX > ADX_MIN)
    df_trending  = df_feat[df_feat["adx"] >= ADX_MIN].copy()
    df_sideways  = df_feat[df_feat["adx"] <  ADX_MIN]
    filtered_pct = round(len(df_trending) / len(df_feat) * 100, 1)

    X_all = df_feat[FEATURE_COLS].values
    y_all = df_feat["target"].values
    n     = len(X_all)

    fold_size = n // (N_SPLITS + 1)
    results   = []

    for fold in range(N_SPLITS):
        train_end  = fold_size * (fold + 1)
        test_start = train_end
        test_end   = min(test_start + fold_size, n)

        if train_end < 100 or test_end - test_start < 30:
            continue

        X_tr = X_all[:train_end]
        y_tr = y_all[:train_end]

        # Test: only high-ADX candles (trending market)
        test_df      = df_feat.iloc[test_start:test_end]
        adx_mask     = test_df["adx"].values >= ADX_MIN
        X_te_all     = X_all[test_start:test_end]
        y_te_all     = y_all[test_start:test_end]

        X_te = X_te_all[adx_mask]
        y_te = y_te_all[adx_mask]

        if len(X_te) < 20:
            continue

        model = xgb.XGBClassifier(
            n_estimators=200, max_depth=4, learning_rate=0.05,
            subsample=0.8, colsample_bytree=0.8,
            eval_metric="logloss", random_state=42, n_jobs=-1,
        )
        model.fit(X_tr, y_tr, verbose=False)

        proba        = model.predict_proba(X_te)[:, 1]
        conf_mask    = (proba >= MIN_CONF) | (proba <= (1 - MIN_CONF))

        if conf_mask.sum() < 10:
            continue

        y_pred = (proba[conf_mask] >= 0.5).astype(int)
        y_true = y_te[conf_mask]

        acc  = accuracy_score(y_true, y_pred)
        prec = precision_score(y_true, y_pred, zero_division=0)

        results.append({
            "fold":        fold + 1,
            "adx_signals": int(adx_mask.sum()),
            "conf_signals":int(conf_mask.sum()),
            "signal_rate": round(conf_mask.sum() / max(len(adx_mask), 1) * 100, 1),
            "accuracy":    round(acc * 100, 2),
            "precision":   round(prec * 100, 2),
        })

    if not results:
        return {"pair": pair, "error": "not enough data after filters"}

    avg_acc  = np.mean([r["accuracy"]  for r in results])
    avg_prec = np.mean([r["precision"] for r in results])
    avg_sig  = np.mean([r["signal_rate"] for r in results])

    return {
        "pair":              pair,
        "trending_candles_pct": filtered_pct,
        "folds":             results,
        "avg_accuracy_pct":  round(avg_acc, 2),
        "avg_precision_pct": round(avg_prec, 2),
        "avg_signal_rate":   round(avg_sig, 1),
        "verdict": (
            "STRONG — deploy this pair"                    if avg_acc >= 60 and avg_prec >= 62 else
            "GOOD — deploy with strict risk management"    if avg_acc >= 57 and avg_prec >= 58 else
            "MARGINAL — paper trade first"                 if avg_acc >= 54 else
            "SKIP — not enough edge on this pair"
        ),
    }

# ─────────────────────────────────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────────────────────────────────

def main():
    print("\n" + "="*62)
    print("  TRADING BOT — ACCURACY ANALYZER v2")
    print("  Improvements: spread-aware target + sessions + ADX filter")
    print("="*62)

    all_results     = {}
    all_fi          = {}
    strong_features = set()
    pair_verdicts   = {}

    for pair in PAIRS:
        print(f"\n{'─'*50}")
        print(f"  {pair}  (spread={SPREAD.get(pair,0.00015):.5f})")
        print(f"{'─'*50}")

        df_raw = fetch_data(pair)
        if df_raw.empty:
            print(f"  ✗ No data — skipping")
            continue

        print(f"  Building features + sessions + spread target...", end=" ")
        try:
            df_feat = build_features(df_raw, pair)
        except Exception as e:
            print(f"✗ {e}")
            continue

        # Check if target has both classes
        vc = df_feat["target"].value_counts()
        if len(vc) < 2:
            print(f"✗ Only one class in target ({vc.to_dict()}) — bad data")
            continue

        trending_pct = round((df_feat["adx"] >= ADX_MIN).mean() * 100, 1)
        print(f"✓ {len(df_feat)} samples  |  "
              f"trending (ADX>{ADX_MIN}): {trending_pct}%  |  "
              f"target: {vc[1]} BUY / {vc[0]} SELL")

        if len(df_feat) < 300:
            print(f"  ✗ Not enough samples — skipping")
            continue

        # Feature importance
        print(f"  Feature importance...", end=" ")
        fi = run_feature_importance(df_feat)
        all_fi[pair] = fi
        top5 = [f["feature"] for f in fi[:5]]
        strong_features.update(top5)
        print(f"✓  Top: {', '.join(top5)}")

        # Walk-forward with ADX filter
        print(f"  Walk-forward ({N_SPLITS} folds, ADX>{ADX_MIN} only)...", end=" ")
        wf = walk_forward(df_feat, pair)
        all_results[pair] = wf
        print(f"✓")

        if "error" not in wf:
            print(f"\n  ┌─ {pair} RESULTS ─────────────────────────")
            print(f"  │  Accuracy  : {wf['avg_accuracy_pct']}%  (random=50%)")
            print(f"  │  Precision : {wf['avg_precision_pct']}%")
            print(f"  │  Signal Rate: {wf['avg_signal_rate']}% of trending candles")
            print(f"  │  Verdict   : {wf['verdict']}")
            print(f"  └────────────────────────────────────────")
            for f in wf.get("folds", []):
                print(f"     Fold {f['fold']}: acc={f['accuracy']}%  "
                      f"prec={f['precision']}%  "
                      f"signals={f['conf_signals']}/{f['adx_signals']}")
            pair_verdicts[pair] = wf["verdict"]
        else:
            print(f"  ✗ {wf['error']}")

    # ── FINAL SUMMARY ─────────────────────────────────────────────────────────
    valid = {p: r for p, r in all_results.items() if "avg_accuracy_pct" in r}
    if not valid:
        print("\n  No valid results.")
        return

    accs  = [r["avg_accuracy_pct"]  for r in valid.values()]
    precs = [r["avg_precision_pct"] for r in valid.values()]

    print("\n" + "="*62)
    print("  FINAL SUMMARY")
    print("="*62)
    print(f"\n  Pairs tested       : {len(valid)}")
    print(f"  Overall Accuracy   : {round(np.mean(accs),2)}%  (was ~52% before)")
    print(f"  Overall Precision  : {round(np.mean(precs),2)}%")

    print(f"\n  Per-pair verdict:")
    for pair, verdict in pair_verdicts.items():
        icon = "✓" if "STRONG" in verdict or "GOOD" in verdict else \
               "~" if "MARGINAL" in verdict else "✗"
        print(f"    {icon}  {pair:<12} — {verdict}")

    print(f"\n  Consistently top features (session + technicals combined):")
    for f in sorted(strong_features):
        is_session = any(x in f for x in ["sess_", "dow_"])
        tag = " [SESSION]" if is_session else ""
        print(f"    ✓ {f}{tag}")

    # Recommendations
    overall_acc = np.mean(accs)
    print(f"\n  What to do next:")
    if overall_acc >= 58:
        print("  1. Train the actual XGBoost model with these features")
        print("  2. Deploy on paper trading for 2 weeks to verify")
        print("  3. Set position size to max 1% per trade")
    elif overall_acc >= 54:
        print("  1. Paper trade only — not ready for live")
        print("  2. Add more data (increase PERIOD to 365d)")
        print("  3. Test on 4H interval instead of 1H")
    else:
        print("  1. Try 4H interval (better signal/noise ratio)")
        print("  2. Reduce pairs — trade only 2-3 best pairs")

    # Save full report
    out_path = os.path.join(os.path.dirname(__file__), "..", "data", "accuracy_report_v2.json")
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "w") as f:
        json.dump({
            "timestamp": datetime.now().isoformat(),
            "config": {"adx_min": ADX_MIN, "min_conf": MIN_CONF,
                       "spread_multiplier": SPREAD_MULTIPLIER, "interval": INTERVAL},
            "overall": {"avg_accuracy": round(np.mean(accs),2),
                        "avg_precision": round(np.mean(precs),2)},
            "pairs": all_results,
            "feature_importance": all_fi,
            "top_features": sorted(strong_features),
        }, f, indent=2)

    print(f"\n  Saved → data/accuracy_report_v2.json")
    print("="*62 + "\n")


if __name__ == "__main__":
    main()
