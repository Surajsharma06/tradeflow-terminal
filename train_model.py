"""
Forex XGBoost Signal Trainer
=============================
Step 1: Label candles (BUY / SELL / HOLD)
Step 2: Feature engineering
Step 3: Train XGBoost (multi-class)
Step 4: Save model + scaler, print full report
"""

import os, warnings, pickle
warnings.filterwarnings("ignore")

import numpy as np
import pandas as pd
from pathlib import Path

# ── Install check ──────────────────────────────────────────────────────────
try:
    import xgboost as xgb
except ImportError:
    os.system("pip3 install xgboost scikit-learn --quiet")
    import xgboost as xgb

from sklearn.preprocessing import RobustScaler
from sklearn.metrics import classification_report, confusion_matrix

# ── Paths ──────────────────────────────────────────────────────────────────
PROCESSED_DIR = Path("/Users/surajbhadola/Downloads/Trading/data/forex/processed")
MODEL_DIR     = Path("/Users/surajbhadola/Downloads/Trading/models")
MODEL_DIR.mkdir(parents=True, exist_ok=True)

MODEL_PATH  = MODEL_DIR / "forex_xgb_model.json"
SCALER_PATH = MODEL_DIR / "forex_scaler.pkl"

# ── Config ─────────────────────────────────────────────────────────────────
LOOK_AHEAD     = 8     # candles to check for TP/SL
TP_MULT        = 1.5   # target: 1.5x ATR
SL_MULT        = 1.0   # stop:   1.0x ATR

ADX_MIN        = 25.0
ATR_PCT_MIN    = 0.05
VALID_SESSIONS = {1, 2, 3}   # London, Overlap, NY

FEATURES = [
    "atr_14", "atr_pct", "adx_14", "ema_align", "rsi_14",
    "macd_hist_dir", "bb_width", "session",
    "dist_prev_day_high", "dist_prev_day_low",
    "dist_prev_week_high", "dist_prev_week_low",
    "dist_round_number", "market_struct",
    "hour_utc", "day_of_week",
]

# ═══════════════════════════════════════════════════════════════════════════
# STEP 1 — LABELING
# ═══════════════════════════════════════════════════════════════════════════

def label_candles(df: pd.DataFrame) -> pd.Series:
    """
    For each row, look LOOK_AHEAD candles forward.
      BUY  = 1  : close rises 1.5x ATR first (without -1x ATR hit)
      SELL = -1 : close falls 1.5x ATR first (without +1x ATR hit)
      HOLD = 0  : everything else
    BUY and SELL are checked INDEPENDENTLY in the same forward window.
    """
    labels    = np.zeros(len(df), dtype="int8")
    closes    = df["close"].values
    atrs      = df["atr_14"].values
    adx_vals  = df["adx_14"].values
    atr_pcts  = df["atr_pct"].values
    sessions  = df["session"].values
    news_risk = df["news_risk"].values if "news_risk" in df.columns else np.zeros(len(df), dtype=bool)

    for i in range(len(df) - LOOK_AHEAD):
        # ── Gate conditions ───────────────────────────────────────────
        if adx_vals[i] <= ADX_MIN:           continue
        if sessions[i] not in VALID_SESSIONS: continue
        if news_risk[i]:                      continue
        if atr_pcts[i] <= ATR_PCT_MIN:        continue

        entry = closes[i]
        atr   = atrs[i]
        if atr <= 0 or np.isnan(atr):         continue

        tp_buy  = entry + TP_MULT * atr   # BUY  target
        sl_buy  = entry - SL_MULT * atr   # BUY  stop (downward)
        tp_sell = entry - TP_MULT * atr   # SELL target
        sl_sell = entry + SL_MULT * atr   # SELL stop (upward)

        # Track BUY and SELL outcomes INDEPENDENTLY
        buy_tp = buy_sl = sell_tp = sell_sl = False

        for j in range(i + 1, i + LOOK_AHEAD + 1):
            c = closes[j]

            # BUY: check TP/SL independently
            if not buy_tp and not buy_sl:
                if c >= tp_buy:
                    buy_tp = True
                elif c <= sl_buy:
                    buy_sl = True

            # SELL: check TP/SL independently
            if not sell_tp and not sell_sl:
                if c <= tp_sell:
                    sell_tp = True
                elif c >= sl_sell:
                    sell_sl = True

            # Stop early if both outcomes determined
            if (buy_tp or buy_sl) and (sell_tp or sell_sl):
                break

        is_buy  = buy_tp  and not buy_sl
        is_sell = sell_tp and not sell_sl

        # If both fire (very volatile candle), prefer the one that hit TP first
        # Simple tiebreak: label as HOLD
        if is_buy and is_sell:
            labels[i] = 0
        elif is_buy:
            labels[i] = 1
        elif is_sell:
            labels[i] = -1
        # else 0 (HOLD)

    return pd.Series(labels, index=df.index, name="label")


# ═══════════════════════════════════════════════════════════════════════════
# STEP 2 — FEATURE ENGINEERING
# ═══════════════════════════════════════════════════════════════════════════

def engineer_features(df: pd.DataFrame) -> pd.DataFrame:
    """Add distance features and time features."""
    c = df["close"]

    # Distances (in price terms, then normalize to ATR units)
    atr = df["atr_14"].replace(0, np.nan)
    df["dist_prev_day_high"]  = (df["prev_day_high"]  - c) / atr
    df["dist_prev_day_low"]   = (c - df["prev_day_low"])   / atr
    df["dist_prev_week_high"] = (df["prev_week_high"] - c) / atr
    df["dist_prev_week_low"]  = (c - df["prev_week_low"])  / atr
    df["dist_round_number"]   = df["round_dist"]           / atr

    # Time features
    if hasattr(df.index, "hour"):
        df["hour_utc"]    = [ts.hour for ts in df.index]
        df["day_of_week"] = [ts.dayofweek for ts in df.index]
    else:
        df["hour_utc"]    = 0
        df["day_of_week"] = 0

    return df


# ═══════════════════════════════════════════════════════════════════════════
# LOAD + PROCESS ALL FILES
# ═══════════════════════════════════════════════════════════════════════════

print(f"\n{'='*70}")
print(f"  Forex XGBoost Signal Trainer")
print(f"{'='*70}\n")

all_frames  = []
pair_stats  = []
label_totals = {"BUY": 0, "SELL": 0, "HOLD": 0}

csv_files = sorted(PROCESSED_DIR.glob("*_processed.csv"))
print(f"  Found {len(csv_files)} processed files\n")

for csv_path in csv_files:
    name = csv_path.stem   # e.g. EURUSD_1h_processed
    parts = name.split("_")
    pair = parts[0]
    tf   = parts[1]

    try:
        df = pd.read_csv(csv_path, index_col=0, parse_dates=True)
        df.index = pd.to_datetime(df.index, utc=True)

        # Only use 15m and 1h for ML (enough resolution, enough data)
        if tf == "1d":
            continue

        # Need at least these cols
        required = ["close", "atr_14", "atr_pct", "adx_14", "session"]
        if not all(c in df.columns for c in required):
            print(f"  ⚠  {name}: missing required columns — skip")
            continue

        # Feature engineering
        df = engineer_features(df)

        # Label
        df["label"] = label_candles(df)

        # Filter to labelable rows only (where conditions could be met)
        # Keep ALL rows for feature matrix but label tells us what to learn
        n_buy  = (df["label"] ==  1).sum()
        n_sell = (df["label"] == -1).sum()
        n_hold = (df["label"] ==  0).sum()

        label_totals["BUY"]  += n_buy
        label_totals["SELL"] += n_sell
        label_totals["HOLD"] += n_hold

        print(f"  ✓  {name:35s}  BUY={n_buy:5d}  SELL={n_sell:5d}  HOLD={n_hold:6d}")

        # Keep pair + tf info
        df["_pair"] = pair
        df["_tf"]   = tf

        all_frames.append(df)
        pair_stats.append({"pair": pair, "tf": tf, "buy": n_buy, "sell": n_sell, "hold": n_hold})

    except Exception as e:
        print(f"  ✗  {name}: {e}")

print(f"\n  Total BUY={label_totals['BUY']:,}  SELL={label_totals['SELL']:,}  HOLD={label_totals['HOLD']:,}")

# ── Combine ────────────────────────────────────────────────────────────────
print(f"\n  Combining all frames...")
combined = pd.concat(all_frames, ignore_index=False)
combined.sort_index(inplace=True)

# ── Feature matrix ─────────────────────────────────────────────────────────
# Drop rows where any feature is NaN
feats_available = [f for f in FEATURES if f in combined.columns]
missing_feats   = [f for f in FEATURES if f not in combined.columns]
if missing_feats:
    print(f"  ⚠  Missing features (will skip): {missing_feats}")

X_all = combined[feats_available].copy()
y_all = combined["label"].copy()

# Drop rows with NaN
mask  = X_all.notna().all(axis=1) & y_all.notna()
X_all = X_all[mask]
y_all = y_all[mask]

# Remap labels: -1→0, 0→1, 1→2  (XGBoost needs 0-indexed classes)
label_map    = {-1: 0, 0: 1, 1: 2}
label_unmap  = {0: "SELL(-1)", 1: "HOLD(0)", 2: "BUY(1)"}
y_mapped     = y_all.map(label_map)

# Ensure all 3 classes are present — pad with tiny synthetic rows if needed
unique_classes = set(y_mapped.unique())
if unique_classes != {0, 1, 2}:
    missing = {0, 1, 2} - unique_classes
    print(f"  ⚠  Adding dummy rows for missing classes: {missing}")
    dummy_X = X_all.iloc[[0] * len(missing)].copy()
    dummy_y = pd.Series(list(missing), index=dummy_X.index)
    X_all   = pd.concat([X_all, dummy_X])
    y_mapped= pd.concat([y_mapped, dummy_y])
    print(f"  ⚠  Class distribution after padding: {y_mapped.value_counts().to_dict()}")

print(f"  Total usable rows : {len(X_all):,}")
print(f"  Features used     : {len(feats_available)}")

# ═══════════════════════════════════════════════════════════════════════════
# STEP 3 — TRAIN
# ═══════════════════════════════════════════════════════════════════════════

# Time-based 80/20 split
split_idx = int(len(X_all) * 0.80)
X_train, X_test = X_all.iloc[:split_idx], X_all.iloc[split_idx:]
y_train, y_test = y_mapped.iloc[:split_idx], y_mapped.iloc[split_idx:]

print(f"\n  Train size : {len(X_train):,}")
print(f"  Test  size : {len(X_test):,}")

# Scale
scaler  = RobustScaler()
X_train_s = scaler.fit_transform(X_train)
X_test_s  = scaler.transform(X_test)

# Class weights for imbalance
counts = y_train.value_counts()
total  = len(y_train)
# Ensure all classes have a weight even if count=0
class_weights = {}
for c in [0, 1, 2]:
    cnt = counts.get(c, 1)
    class_weights[c] = total / (3 * max(cnt, 1))
sample_weights = y_train.map(class_weights).fillna(1.0).values

print(f"\n  Class weights: SELL={class_weights[0]:.2f}  HOLD={class_weights[1]:.2f}  BUY={class_weights[2]:.2f}")
print(f"\n  Training XGBoost (1000 estimators, depth=5)...")

model = xgb.XGBClassifier(
    n_estimators      = 1000,
    max_depth         = 5,
    learning_rate     = 0.03,
    min_child_weight  = 15,
    subsample         = 0.8,
    colsample_bytree  = 0.8,
    objective         = "multi:softmax",
    num_class         = 3,
    eval_metric       = "mlogloss",
    use_label_encoder = False,
    random_state      = 42,
    n_jobs            = -1,
    early_stopping_rounds = 30,
    verbosity         = 0,
)

model.fit(
    X_train_s, y_train,
    sample_weight   = sample_weights,
    eval_set        = [(X_test_s, y_test)],
    verbose         = False,
)

print(f"  Best iteration: {model.best_iteration}")

# ═══════════════════════════════════════════════════════════════════════════
# STEP 4 — SAVE + REPORT
# ═══════════════════════════════════════════════════════════════════════════

# Save
model.save_model(str(MODEL_PATH))
with open(SCALER_PATH, "wb") as f:
    pickle.dump(scaler, f)
print(f"\n  ✓ Model saved  : {MODEL_PATH}")
print(f"  ✓ Scaler saved : {SCALER_PATH}")

# Predict
y_pred = model.predict(X_test_s)

print(f"\n{'='*70}")
print(f"  MODEL PERFORMANCE REPORT")
print(f"{'='*70}")

# Overall
print(f"\n  Overall accuracy: {(y_pred == y_test.values).mean()*100:.2f}%\n")

# Per-class
target_names = ["SELL(-1)", "HOLD(0)", "BUY(+1)"]
print(classification_report(y_test, y_pred, target_names=target_names, digits=3))

# Confusion matrix
cm = confusion_matrix(y_test, y_pred)
print(f"  Confusion Matrix (rows=actual, cols=predicted):")
print(f"  {'':12s} {'SELL':>8s} {'HOLD':>8s} {'BUY':>8s}")
for i, row_name in enumerate(["SELL", "HOLD", "BUY"]):
    print(f"  {row_name:12s} {cm[i][0]:>8d} {cm[i][1]:>8d} {cm[i][2]:>8d}")

# Feature importance
print(f"\n  Top 10 Feature Importances:")
importance = model.feature_importances_
feat_imp = pd.DataFrame({
    "feature":    feats_available,
    "importance": importance
}).sort_values("importance", ascending=False).head(10)
for _, row in feat_imp.iterrows():
    bar = "█" * int(row["importance"] * 300)
    print(f"  {row['feature']:30s} {row['importance']:.4f}  {bar}")

# Per-pair breakdown
print(f"\n  Per-pair Label Distribution (15m + 1h combined):")
df_ps = pd.DataFrame(pair_stats)
if not df_ps.empty:
    summary = df_ps.groupby("pair")[["buy","sell","hold"]].sum()
    summary["total"] = summary.sum(axis=1)
    summary["buy%"]  = (summary["buy"]  / summary["total"] * 100).round(1)
    summary["sell%"] = (summary["sell"] / summary["total"] * 100).round(1)
    print(f"\n  {'Pair':10s} {'BUY':>7s} {'SELL':>7s} {'HOLD':>7s} {'BUY%':>6s} {'SELL%':>6s}")
    print(f"  {'-'*50}")
    for pair, row in summary.iterrows():
        print(f"  {pair:10s} {int(row['buy']):>7d} {int(row['sell']):>7d} {int(row['hold']):>7d} {row['buy%']:>5.1f}% {row['sell%']:>5.1f}%")

print(f"\n{'='*70}")
print(f"  Training complete!")
print(f"  Model : {MODEL_PATH}")
print(f"  Scaler: {SCALER_PATH}")
print(f"{'='*70}\n")
