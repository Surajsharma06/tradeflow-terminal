"""
Commodity Analysis Engine — Gold (XAU), Silver (XAG), WTI Crude, Natural Gas (NG)

Why each asset is different:
  Gold/Silver  — macro/rate-driven: DXY (inverse), real yields, FOMC sensitivity.
                 Silver adds industrial-cycle beta on top of the gold direction.
  WTI Crude   — supply/geopolitics: OPEC+ meetings, EIA weekly storage draw/build,
                 curve shape (backwardation = tightening physical market, bullish).
  Natural Gas  — weather/seasonality: winter heating peak (Nov-Feb), secondary summer
                 cooling bump, spring/fall bearish. ATR stop widened ×2 for NG.

Data sources:
  OHLCV        — yfinance continuous front-month futures (GC=F, SI=F, CL=F, NG=F)
  COT          — CFTC public SODA API (publicreporting.cftc.gov) — weekly, free
  Macro        — yfinance (DX-Y.NYB for DXY, ^TNX for 10-Year yield)
  Seasonality  — computed from 10 years of yfinance monthly history
  Futures Curve— yfinance deferred-month contracts dynamically built
  Calendar     — algorithmic (EIA/FOMC/OPEC weekly + hardcoded 2026 dates)
"""

from __future__ import annotations

import logging
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date, datetime, timedelta, timezone
from typing import Optional

import httpx
import numpy as np
import pandas as pd
import yfinance as yf

from app.domain.indicators.technical import (
    ema, sma, rsi, macd, bollinger_bands, atr, adx, volume_sma_ratio,
)

logger = logging.getLogger(__name__)
IST = timezone(timedelta(hours=5, minutes=30))

# CME/COMEX futures month codes
MONTH_CODES = {1:'F',2:'G',3:'H',4:'J',5:'K',6:'M',7:'N',8:'Q',9:'U',10:'V',11:'X',12:'Z'}

ASSETS: dict[str, dict] = {
    "XAU": {
        "name": "Gold",
        "unit": "troy oz",
        "yf_1h":  "GC=F",
        "yf_hist": "GC=F",
        "fut_root": "GC",
        "cot_keyword": "GOLD",
        "atr_mult": 1.5,
        "min_rr": 2.0,
        "event_mutes": ["FOMC", "CPI", "NFP"],
        "macro_driver": "RATES_DXY",
        "seasonal_note": "Historically firmer: Aug–Oct (Indian festive/wedding), Nov–Jan (year-end + CNY flows). Seasonally weak: Mar–Jun.",
    },
    "XAG": {
        "name": "Silver",
        "unit": "troy oz",
        "yf_1h":  "SI=F",
        "yf_hist": "SI=F",
        "fut_root": "SI",
        "cot_keyword": "SILVER",
        "atr_mult": 1.5,
        "min_rr": 2.0,
        "event_mutes": ["FOMC", "CPI", "NFP"],
        "macro_driver": "RATES_DXY",
        "seasonal_note": "Tracks gold direction with higher beta (±30% wider swings). Industrial component adds exposure to manufacturing PMI cycle.",
    },
    "WTI": {
        "name": "WTI Crude Oil",
        "unit": "barrel",
        "yf_1h":  "CL=F",
        "yf_hist": "CL=F",
        "fut_root": "CL",
        "cot_keyword": "CRUDE OIL",
        "atr_mult": 1.5,
        "min_rr": 2.0,
        "event_mutes": ["OPEC", "EIA_PETRO"],
        "macro_driver": "SUPPLY_DEMAND",
        "seasonal_note": "Spring dip (Mar–Apr refinery maintenance); summer driving demand peak (Jun–Aug); winter support from heating oil demand.",
    },
    "NG": {
        "name": "Natural Gas",
        "unit": "mmBtu",
        "yf_1h":  "NG=F",
        "yf_hist": "NG=F",
        "fut_root": "NG",
        "cot_keyword": "NATURAL GAS",
        "atr_mult": 2.0,   # widened — extreme vol profile
        "min_rr": 2.0,
        "event_mutes": ["EIA_NATGAS"],
        "macro_driver": "WEATHER_STORAGE",
        "seasonal_note": "Primary demand peak: Nov–Feb (heating). Secondary: Jun–Aug (cooling). Seasonally very weak: Mar–May, Sep–Oct injection season.",
    },
}

# ── Known 2026 scheduled event dates ─────────────────────────────────
FOMC_DATES_2026 = [
    date(2026, 1, 28), date(2026, 3, 18), date(2026, 4, 29),
    date(2026, 6, 17), date(2026, 7, 29), date(2026, 9, 16),
    date(2026, 10, 28), date(2026, 12, 9),
]
OPEC_DATES_2026 = [
    date(2026, 3, 4), date(2026, 6, 3), date(2026, 9, 2), date(2026, 12, 2),
]
# ─────────────────────────────────────────────────────────────────────


# ══════════════════════════════════════════════════════════════════════
#  Caches
# ══════════════════════════════════════════════════════════════════════
_cot_cache:        dict[str, tuple[float, dict]] = {}
_seasonal_cache:   dict[str, tuple[float, dict]] = {}
_macro_cache:      tuple[float, dict] | None = None
_curve_cache:      dict[str, tuple[float, dict]] = {}

_COT_TTL      = 24 * 3600.0
_SEASONAL_TTL = 24 * 3600.0
_MACRO_TTL    = 3600.0
_CURVE_TTL    = 3600.0


# ══════════════════════════════════════════════════════════════════════
#  Data fetching
# ══════════════════════════════════════════════════════════════════════

def _fetch_commodity(symbol: str, period: str = "60d", interval: str = "1h") -> Optional[pd.DataFrame]:
    for attempt in range(2):
        try:
            df = yf.Ticker(symbol).history(period=period, interval=interval, auto_adjust=True)
            if df is None or df.empty:
                if attempt == 0:
                    time.sleep(1)
                    continue
                return None
            # Handle both regular Index and MultiIndex column names
            if hasattr(df.columns, 'levels'):
                df.columns = [c[0].lower() if isinstance(c, tuple) else c.lower() for c in df.columns]
            else:
                df.columns = [c.lower() for c in df.columns]
            cols = [c for c in ("open", "high", "low", "close", "volume") if c in df.columns]
            if not cols:
                return None
            df = df[cols].copy().dropna()
            return df if len(df) >= 20 else None
        except Exception as exc:
            logger.warning("_fetch_commodity %s attempt %d failed: %s", symbol, attempt + 1, exc)
            if attempt == 0:
                time.sleep(1)
    return None


# ── COT (CFTC Disaggregated Futures) ─────────────────────────────────

def _get_cot_data(symbol: str, keyword: str) -> dict:
    """CFTC public SODA API — Disaggregated Futures-Only report. Free, no auth."""
    hit = _cot_cache.get(symbol)
    if hit and (time.time() - hit[0]) < _COT_TTL:
        return hit[1]

    result: dict = {"available": False, "symbol": symbol}
    try:
        url = "https://publicreporting.cftc.gov/resource/72hh-3qpy.json"
        params = {
            "$where": f"upper(market_and_exchange_names) like upper('%{keyword}%')",
            "$order": "report_date_as_yyyy_mm_dd DESC",
            "$limit": "156",
        }
        with httpx.Client(timeout=8) as c:
            r = c.get(url, params=params)

        if r.status_code != 200 or not r.json():
            raise ValueError(f"CFTC {r.status_code}")

        rows = r.json()
        # Managed Money = non-commercial equivalent in disaggregated report
        def _int(row: dict, key: str) -> int:
            return int(float(row.get(key, 0) or 0))

        latest = rows[0]
        mm_long  = _int(latest, "m_money_positions_long_all")
        mm_short = _int(latest, "m_money_positions_short_all")
        mm_net   = mm_long - mm_short

        prod_long  = _int(latest, "prod_merc_positions_long_al")
        prod_short = _int(latest, "prod_merc_positions_short_al")
        comm_net   = prod_long - prod_short

        # Trailing 3-year percentile of MM net
        hist_nets = []
        for row in rows:
            try:
                hist_nets.append(_int(row, "m_money_positions_long_all") - _int(row, "m_money_positions_short_all"))
            except Exception:
                pass

        net_min, net_max = min(hist_nets), max(hist_nets)
        net_range = max(net_max - net_min, 1)
        pctile = (mm_net - net_min) / net_range * 100

        # Week-over-week change in MM net
        prev_mm_net = None
        if len(rows) > 1:
            prev_mm_net = _int(rows[1], "m_money_positions_long_all") - _int(rows[1], "m_money_positions_short_all")

        wow_pct = ((mm_net - prev_mm_net) / max(abs(prev_mm_net), 1) * 100) if prev_mm_net is not None else 0.0

        ext_dir = ("EXTREME_LONG" if pctile >= 80 else "EXTREME_SHORT" if pctile <= 20 else "NORMAL")
        cot_signal = (
            "CONTRARIAN_SELL" if ext_dir == "EXTREME_LONG" else
            "CONTRARIAN_BUY"  if ext_dir == "EXTREME_SHORT" else
            "MOMENTUM_BUY"    if wow_pct >= 20 else
            "MOMENTUM_SELL"   if wow_pct <= -20 else
            "NEUTRAL"
        )

        result = {
            "available": True,
            "symbol": symbol,
            "report_date": latest.get("report_date_as_yyyy_mm_dd"),
            "mm_net": mm_net,
            "mm_long": mm_long,
            "mm_short": mm_short,
            "commercial_net": comm_net,
            "mm_percentile": round(pctile, 1),
            "extreme": pctile >= 80 or pctile <= 20,
            "extreme_direction": ext_dir,
            "wow_change_pct": round(wow_pct, 1),
            "wow_large_move": abs(wow_pct) >= 20,
            "signal": cot_signal,
            "confluence_dir": (
                "BEARISH" if cot_signal in ("CONTRARIAN_SELL", "MOMENTUM_SELL") else
                "BULLISH" if cot_signal in ("CONTRARIAN_BUY",  "MOMENTUM_BUY")  else
                "NEUTRAL"
            ),
        }
    except Exception as exc:
        logger.warning("COT fetch failed for %s: %s", symbol, exc)
        result = {"available": False, "symbol": symbol, "error": str(exc), "confluence_dir": "NEUTRAL"}

    _cot_cache[symbol] = (time.time(), result)
    return result


# ── Seasonality ───────────────────────────────────────────────────────

def _compute_seasonality(symbol: str, yf_symbol: str) -> dict:
    hit = _seasonal_cache.get(symbol)
    if hit and (time.time() - hit[0]) < _SEASONAL_TTL:
        return hit[1]

    result: dict = {"available": False}
    try:
        df = yf.Ticker(yf_symbol).history(period="10y", interval="1mo", auto_adjust=True)
        if df is None or df.empty or len(df) < 24:
            raise ValueError("insufficient history")
        df.columns = [c.lower() for c in df.columns]
        df["month"] = df.index.month
        df["return"] = df["close"].pct_change()
        avg = df.groupby("month")["return"].mean()

        cur_month = datetime.now().month
        cur_avg = float(avg.get(cur_month, 0))
        monthly = {int(m): round(float(v), 4) for m, v in avg.items()}

        # Seasonality alignment (compare YTD actual to historical for this month)
        alignment = (
            "BULLISH_SEASON"   if cur_avg >= 0.005 else
            "BEARISH_SEASON"   if cur_avg <= -0.005 else
            "NEUTRAL_SEASON"
        )

        result = {
            "available": True,
            "monthly_avg": monthly,
            "current_month": cur_month,
            "current_month_avg_pct": round(cur_avg * 100, 2),
            "alignment": alignment,
            "confluence_dir": (
                "BULLISH" if alignment == "BULLISH_SEASON" else
                "BEARISH" if alignment == "BEARISH_SEASON" else
                "NEUTRAL"
            ),
        }
    except Exception as exc:
        logger.warning("Seasonality failed for %s: %s", symbol, exc)
        result = {"available": False, "error": str(exc), "confluence_dir": "NEUTRAL"}

    _seasonal_cache[symbol] = (time.time(), result)
    return result


# ── Futures Curve (Contango / Backwardation) ──────────────────────────

def _get_futures_curve(symbol: str, front_price: float) -> dict:
    hit = _curve_cache.get(symbol)
    if hit and (time.time() - hit[0]) < _CURVE_TTL:
        return hit[1]

    root = ASSETS[symbol]["fut_root"]
    today = datetime.now()
    result: dict = {"shape": "UNAVAILABLE", "signal": "NEUTRAL", "confluence_dir": "NEUTRAL"}

    prices: list[tuple[str, float]] = []
    for offset in range(1, 4):
        m = (today.month + offset - 1) % 12 + 1
        y = today.year + (today.month + offset - 1) // 12
        code = MONTH_CODES[m]
        ticker = f"{root}{code}{str(y)[2:]}=F"
        try:
            df_d = yf.Ticker(ticker).history(period="5d", interval="1d", auto_adjust=True)
            if df_d is not None and not df_d.empty:
                prices.append((ticker, float(df_d["Close"].iloc[-1])))
        except Exception:
            pass

    if prices:
        t1, p1 = prices[0]
        spread = p1 - front_price
        spread_pct = round(spread / max(front_price, 0.01) * 100, 3)
        shape = "CONTANGO" if spread > 0 else "BACKWARDATION"
        # Backwardation = near-term physical tightness = bullish, especially for crude
        signal = "BULLISH" if shape == "BACKWARDATION" else "NEUTRAL"
        result = {
            "shape": shape,
            "front_price": round(front_price, 3),
            "deferred_ticker": t1,
            "deferred_price": round(p1, 3),
            "spread": round(spread, 3),
            "spread_pct": spread_pct,
            "signal": signal,
            "confluence_dir": "BULLISH" if shape == "BACKWARDATION" else "NEUTRAL",
            "note": (
                f"Backwardation: front ${front_price:.2f} > deferred ({t1}) ${p1:.2f} "
                f"— near-term scarcity, physically tight market"
                if shape == "BACKWARDATION" else
                f"Contango: deferred ({t1}) ${p1:.2f} > front ${front_price:.2f} "
                f"(+{spread_pct:.2f}%) — cost-of-carry, normal market structure"
            ),
        }

    _curve_cache[symbol] = (time.time(), result)
    return result


# ── Macro data (DXY, 10Y yield) ───────────────────────────────────────

def _get_macro_data() -> dict:
    global _macro_cache
    if _macro_cache and (time.time() - _macro_cache[0]) < _MACRO_TTL:
        return _macro_cache[1]

    result: dict = {"available": False}
    try:
        dxy_df  = yf.Ticker("DX-Y.NYB").history(period="60d", interval="1d", auto_adjust=True)
        t10_df  = yf.Ticker("^TNX").history(period="60d", interval="1d", auto_adjust=True)

        dxy_now = float(dxy_df["Close"].iloc[-1])  if dxy_df  is not None and not dxy_df.empty  else None
        dxy_ago = float(dxy_df["Close"].iloc[-10]) if dxy_df  is not None and len(dxy_df) >= 10 else None
        t10_now = float(t10_df["Close"].iloc[-1])  if t10_df  is not None and not t10_df.empty  else None
        t10_ago = float(t10_df["Close"].iloc[-10]) if t10_df  is not None and len(t10_df) >= 10 else None

        dxy_trend = (
            "RISING" if dxy_now and dxy_ago and dxy_now > dxy_ago * 1.002 else
            "FALLING" if dxy_now and dxy_ago and dxy_now < dxy_ago * 0.998 else
            "FLAT"
        )
        yield_trend = (
            "RISING" if t10_now and t10_ago and t10_now > t10_ago + 0.05 else
            "FALLING" if t10_now and t10_ago and t10_now < t10_ago - 0.05 else
            "FLAT"
        )

        # DXY rising = headwind for gold/silver (inverse correlation)
        # Real yields rising = headwind for gold (opportunity cost)
        gold_macro_bull = (dxy_trend == "FALLING") and (yield_trend in ("FALLING", "FLAT"))
        gold_macro_bear = (dxy_trend == "RISING")  and (yield_trend == "RISING")

        result = {
            "available": True,
            "dxy": round(dxy_now, 2) if dxy_now else None,
            "dxy_trend": dxy_trend,
            "dxy_10d_change_pct": round((dxy_now / dxy_ago - 1) * 100, 2) if dxy_now and dxy_ago else None,
            "yield_10y": round(t10_now, 3) if t10_now else None,
            "yield_trend": yield_trend,
            "yield_10d_change_bp": round((t10_now - t10_ago) * 100, 1) if t10_now and t10_ago else None,
            "gold_silver_confluence": "BULLISH" if gold_macro_bull else ("BEARISH" if gold_macro_bear else "NEUTRAL"),
            "note": (
                "DXY falling + yields flat/falling → macro tailwind for gold/silver" if gold_macro_bull else
                "DXY rising + yields rising → macro headwind for gold/silver" if gold_macro_bear else
                "Mixed macro signals — DXY and yields not clearly aligned"
            ),
        }
    except Exception as exc:
        logger.warning("Macro data failed: %s", exc)
        result = {"available": False, "error": str(exc), "gold_silver_confluence": "NEUTRAL"}

    _macro_cache = (time.time(), result)
    return result


# ══════════════════════════════════════════════════════════════════════
#  Economic Calendar
# ══════════════════════════════════════════════════════════════════════

def _first_friday(year: int, month: int) -> date:
    d = date(year, month, 1)
    while d.weekday() != 4:
        d += timedelta(days=1)
    return d


def _second_wednesday(year: int, month: int) -> date:
    """Approximate CPI release date — usually around the 10th–14th."""
    d = date(year, month, 10)
    while d.weekday() != 2:
        d += timedelta(days=1)
    return d


def get_upcoming_events(horizon_days: int = 7) -> list[dict]:
    """Return all commodity-relevant events in the next `horizon_days` days."""
    today = date.today()
    window_end = today + timedelta(days=horizon_days)
    events: list[dict] = []

    # EIA Petroleum (every Wednesday)
    # EIA Nat Gas Storage (every Thursday)
    d = today
    while d <= window_end:
        if d.weekday() == 2:  # Wednesday
            events.append({
                "date": d.isoformat(), "event": "EIA Petroleum Status Report",
                "type": "EIA_PETRO", "affects": ["WTI"],
                "mutes": True, "window_h": 3,
                "note": "EIA weekly crude/product storage data (~10:30 AM ET). Mutes new WTI signals for 3h.",
            })
        if d.weekday() == 3:  # Thursday
            events.append({
                "date": d.isoformat(), "event": "EIA Natural Gas Storage Report",
                "type": "EIA_NATGAS", "affects": ["NG"],
                "mutes": True, "window_h": 3,
                "note": "EIA weekly storage injection/draw (~10:30 AM ET). Mutes NG signals for 3h.",
            })
        d += timedelta(days=1)

    # NFP (first Friday of month)
    for offset in range(3):
        mo = (today.month + offset - 1) % 12 + 1
        yr = today.year + (today.month + offset - 1) // 12
        nfp_d = _first_friday(yr, mo)
        if today <= nfp_d <= window_end:
            events.append({
                "date": nfp_d.isoformat(), "event": "Non-Farm Payrolls (NFP)",
                "type": "NFP", "affects": ["XAU", "XAG"],
                "mutes": True, "window_h": 2,
                "note": "Labour data moves rate-cut expectations → Gold/Silver. Signal muted for 2h after release.",
            })

    # CPI (roughly 2nd Wednesday of month)
    for offset in range(3):
        mo = (today.month + offset - 1) % 12 + 1
        yr = today.year + (today.month + offset - 1) // 12
        cpi_d = _second_wednesday(yr, mo)
        if today <= cpi_d <= window_end:
            events.append({
                "date": cpi_d.isoformat(), "event": "US CPI Release",
                "type": "CPI", "affects": ["XAU", "XAG"],
                "mutes": True, "window_h": 2,
                "note": "CPI shapes FOMC expectations → largest single event for Gold.",
            })

    # FOMC (hardcoded 2026)
    for fd in FOMC_DATES_2026:
        if today <= fd <= window_end:
            events.append({
                "date": fd.isoformat(), "event": "FOMC Meeting Decision",
                "type": "FOMC", "affects": ["XAU", "XAG"],
                "mutes": True, "window_h": 24,
                "note": "Fed rate decision. All gold/silver signals muted 24h around FOMC.",
            })

    # OPEC+ (hardcoded 2026)
    for od in OPEC_DATES_2026:
        if today <= od <= window_end + timedelta(days=1):
            events.append({
                "date": od.isoformat(), "event": "OPEC+ Meeting",
                "type": "OPEC", "affects": ["WTI"],
                "mutes": True, "window_h": 24,
                "note": "OPEC+ production decision. WTI signals muted 24h around meeting.",
            })

    events.sort(key=lambda e: e["date"])
    return events


def _muted_for_symbol(symbol: str, events: list[dict]) -> Optional[dict]:
    """Return the muting event if this symbol is within its mute window, else None."""
    today = date.today()
    mute_types = set(ASSETS[symbol].get("event_mutes", []))
    for ev in events:
        if ev.get("type") not in mute_types:
            continue
        if symbol not in ev.get("affects", []):
            continue
        ev_date = date.fromisoformat(ev["date"])
        window_h = ev.get("window_h", 24)
        delta_h = (ev_date - today).days * 24
        if -window_h <= delta_h <= window_h:
            return ev
    return None


# ══════════════════════════════════════════════════════════════════════
#  Indicator helpers
# ══════════════════════════════════════════════════════════════════════

def _rolling_vwap(df: pd.DataFrame, window: int = 24) -> pd.Series:
    tp = (df["high"] + df["low"] + df["close"]) / 3.0
    vol = df["volume"].replace(0, np.nan)
    return (tp * vol).rolling(window).sum() / vol.rolling(window).sum()


def _fibonacci(df: pd.DataFrame, lookback: int = 100) -> dict:
    recent = df.tail(lookback)
    sh, sl = float(recent["high"].max()), float(recent["low"].min())
    d = sh - sl
    return {
        "swing_high": round(sh, 3), "swing_low": round(sl, 3),
        "fib_786": round(sh - 0.786 * d, 3),
        "fib_618": round(sh - 0.618 * d, 3),
        "fib_500": round(sh - 0.500 * d, 3),
        "fib_382": round(sh - 0.382 * d, 3),
    }


def _rsi_divergence(prices: pd.Series, rsi_s: pd.Series, lookback: int = 30) -> str:
    if len(prices) < lookback:
        return "NONE"
    p, r = prices.iloc[-lookback:], rsi_s.iloc[-lookback:]
    mid = lookback // 2
    if p.iloc[-1] < p.iloc[:mid].min() and r.iloc[-1] > r.iloc[:mid].min():
        return "BULLISH_DIVERGENCE"
    if p.iloc[-1] > p.iloc[:mid].max() and r.iloc[-1] < r.iloc[:mid].max():
        return "BEARISH_DIVERGENCE"
    return "NONE"


def _trend_4h(yf_symbol: str) -> str:
    df = _fetch_commodity(yf_symbol, "180d", "4h")
    if df is None or len(df) < 50:
        return "NEUTRAL"
    cl = df["close"]
    e50 = ema(cl, 50); p = float(cl.iloc[-1]); e50v = float(e50.iloc[-1])
    e200v = float(ema(cl, 200).iloc[-1]) if len(cl) >= 200 else None
    if p > e50v:
        return "STRONG_BULLISH" if e200v and p > e200v else "BULLISH"
    if p < e50v:
        return "STRONG_BEARISH" if e200v and p < e200v else "BEARISH"
    return "NEUTRAL"


# ══════════════════════════════════════════════════════════════════════
#  Main analysis
# ══════════════════════════════════════════════════════════════════════

def analyze_commodity(
    symbol: str,
    events: Optional[list[dict]] = None,
    account_balance: float = 10_000.0,
    risk_pct: float = 1.0,
) -> dict:
    """Full 9-factor analysis for one commodity."""
    cfg = ASSETS.get(symbol)
    if not cfg:
        return {"error": f"Unknown symbol {symbol}"}

    df_1h = _fetch_commodity(cfg["yf_1h"], "60d", "1h")
    if df_1h is None or len(df_1h) < 50:
        return {"error": f"Insufficient 1H data for {symbol}", "symbol": symbol}

    close = df_1h["close"]
    price = float(close.iloc[-1])

    # ── Technical indicators ──
    e9  = ema(close, 9);  e21 = ema(close, 21)
    e50 = ema(close, 50); e200 = ema(close, 200) if len(close) >= 200 else pd.Series([np.nan]*len(close), index=close.index)
    rsi14 = rsi(close, 14)
    ml, ms, mh = macd(close, 12, 26, 9)
    bb_u, bb_m, bb_l, bb_bw, _ = bollinger_bands(close, 20, 2.0)
    atr14 = atr(df_1h, 14)
    vol_r = volume_sma_ratio(df_1h, 20)
    vwap24 = _rolling_vwap(df_1h, 24)

    def _f(s: pd.Series):
        v = s.iloc[-1]; return None if pd.isna(v) else float(v)

    cur_e9, cur_e21, cur_e50 = _f(e9), _f(e21), _f(e50)
    cur_e200 = _f(e200)
    cur_rsi  = _f(rsi14) or 50.0
    cur_ml, cur_ms, cur_mh = _f(ml) or 0.0, _f(ms) or 0.0, _f(mh) or 0.0
    prev_mh  = float(mh.iloc[-2]) if len(mh) > 1 and not pd.isna(mh.iloc[-2]) else 0.0
    cur_bbu  = _f(bb_u) or price; cur_bbm = _f(bb_m) or price; cur_bbl = _f(bb_l) or price
    cur_bbbw = _f(bb_bw) or 0.0
    cur_atr  = _f(atr14) or price * 0.02
    cur_volr = _f(vol_r) or 1.0
    cur_vwap = _f(vwap24)

    bw_hist = bb_bw.dropna().values
    bb_squeeze = cur_bbbw < float(np.percentile(bw_hist[-100:], 20)) if len(bw_hist) >= 20 else False

    macd_cross = "NONE"
    if prev_mh < 0 and cur_mh > 0: macd_cross = "BULLISH_CROSS"
    elif prev_mh > 0 and cur_mh < 0: macd_cross = "BEARISH_CROSS"

    ema_bull = all(x is not None for x in (cur_e9, cur_e21, cur_e50)) and cur_e9 > cur_e21 > cur_e50
    ema_bear = all(x is not None for x in (cur_e9, cur_e21, cur_e50)) and cur_e9 < cur_e21 < cur_e50
    trend_1h = "BULLISH" if ema_bull else ("BEARISH" if ema_bear else "NEUTRAL")
    t4h = _trend_4h(cfg["yf_1h"])
    rsi_div = _rsi_divergence(close, rsi14)

    # ── Fundamental data ──
    cot = _get_cot_data(symbol, cfg["cot_keyword"])
    seasonal = _compute_seasonality(symbol, cfg["yf_hist"])
    curve = _get_futures_curve(symbol, price)
    macro = _get_macro_data() if symbol in ("XAU", "XAG") else None

    # ── Confluence buckets (technical + fundamental) ──
    bull_tech: list[str] = []
    bear_tech: list[str] = []
    bull_fund: list[str] = []
    bear_fund: list[str] = []

    # 1. EMA alignment + 200-SMA context
    if ema_bull:  bull_tech.append(f"EMA 9 > EMA 21 > EMA 50 — bullish stack (trend_1h={trend_1h})")
    if ema_bear:  bear_tech.append(f"EMA 9 < EMA 21 < EMA 50 — bearish stack")
    if cur_e200:
        if price > cur_e200: bull_tech.append(f"Price above EMA 200 ({cur_e200:.2f}) — institutional uptrend zone")
        else:                 bear_tech.append(f"Price below EMA 200 ({cur_e200:.2f}) — institutional downtrend zone")

    # 2. RSI + divergence
    if 50 < cur_rsi < 70: bull_tech.append(f"RSI {cur_rsi:.1f} in bull momentum zone (50-70)")
    elif 30 < cur_rsi < 50: bear_tech.append(f"RSI {cur_rsi:.1f} in bear momentum zone (30-50)")
    if rsi_div == "BULLISH_DIVERGENCE": bull_tech.append("RSI bullish divergence — price lower low, RSI higher low")
    if rsi_div == "BEARISH_DIVERGENCE": bear_tech.append("RSI bearish divergence — price higher high, RSI lower high")

    # 3. MACD
    if cur_mh > 0 and cur_ml > cur_ms: bull_tech.append(f"MACD histogram positive ({cur_mh:+.2f}), line above signal")
    if cur_mh < 0 and cur_ml < cur_ms: bear_tech.append(f"MACD histogram negative ({cur_mh:+.2f}), line below signal")
    if macd_cross == "BULLISH_CROSS": bull_tech.append("MACD bullish histogram crossover this bar")
    if macd_cross == "BEARISH_CROSS": bear_tech.append("MACD bearish histogram crossover this bar")

    # 4. Bollinger Bands
    if price <= cur_bbl:  bull_tech.append(f"Price at/below lower Bollinger band ({cur_bbl:.2f}) — oversold extreme")
    elif price >= cur_bbu: bear_tech.append(f"Price at/above upper Bollinger band ({cur_bbu:.2f}) — overbought extreme")
    if bb_squeeze:
        bull_tech.append(f"BB squeeze (bw={cur_bbbw:.4f}) — volatility coiling, breakout imminent")
        bear_tech.append(f"BB squeeze (bw={cur_bbbw:.4f}) — volatility coiling, breakout imminent")

    # 5. VWAP + Volume
    if cur_vwap:
        if price > cur_vwap: bull_tech.append(f"Price ({price:.2f}) above 24H VWAP ({cur_vwap:.2f})")
        else:                  bear_tech.append(f"Price ({price:.2f}) below 24H VWAP ({cur_vwap:.2f})")
    if cur_volr >= 2.0:
        lbl = f"Volume spike {cur_volr:.1f}× avg — institutional activity (watch direction)"
        bull_tech.append(lbl); bear_tech.append(lbl)

    # 6. COT (FUNDAMENTAL)
    if cot.get("available"):
        cd = cot.get("confluence_dir", "NEUTRAL")
        pct = cot.get("mm_percentile", 50)
        wow = cot.get("wow_change_pct", 0)
        if cd == "BULLISH":
            msg = (f"COT: Managed Money EXTREMELY SHORT (MM net={cot['mm_net']:,}, {pct:.0f}th pctile) — contrarian buy signal"
                   if cot.get("extreme_direction") == "EXTREME_SHORT" else
                   f"COT: MM net position surged +{wow:.0f}% WoW — momentum buying")
            bull_fund.append(msg)
        elif cd == "BEARISH":
            msg = (f"COT: Managed Money EXTREMELY LONG (MM net={cot['mm_net']:,}, {pct:.0f}th pctile) — contrarian sell signal"
                   if cot.get("extreme_direction") == "EXTREME_LONG" else
                   f"COT: MM net position fell {wow:.0f}% WoW — momentum selling")
            bear_fund.append(msg)

    # 7. Futures Curve (FUNDAMENTAL)
    if curve.get("shape") not in ("UNAVAILABLE", None):
        cd = curve.get("confluence_dir", "NEUTRAL")
        if cd == "BULLISH":
            bull_fund.append(f"Futures curve: {curve['shape']} — {curve.get('note','')}")
        elif cd == "NEUTRAL" and curve["shape"] == "CONTANGO":
            # Contango is neutral/slightly bearish only for physical commodities
            if symbol in ("WTI", "NG"):
                bear_fund.append(f"Futures curve: CONTANGO ({curve.get('spread_pct',0):+.2f}%) — cost-of-carry, no near-term scarcity")

    # 8. Seasonality (STRUCTURAL/FUNDAMENTAL)
    if seasonal.get("available"):
        cd = seasonal.get("confluence_dir", "NEUTRAL")
        avg_pct = seasonal.get("current_month_avg_pct", 0)
        mo_name = datetime.now().strftime("%B")
        if cd == "BULLISH":
            bull_fund.append(f"Seasonality: {mo_name} historically +{avg_pct:.1f}% avg for {ASSETS[symbol]['name']}")
        elif cd == "BEARISH":
            bear_fund.append(f"Seasonality: {mo_name} historically {avg_pct:.1f}% avg for {ASSETS[symbol]['name']}")

    # 9. Macro (FUNDAMENTAL — gold/silver only)
    if macro and macro.get("available"):
        cd = macro.get("gold_silver_confluence", "NEUTRAL")
        if cd == "BULLISH":
            bull_fund.append(f"Macro: DXY {macro['dxy_trend']} + yields {macro['yield_trend']} → tailwind for {symbol}")
        elif cd == "BEARISH":
            bear_fund.append(f"Macro: DXY {macro['dxy_trend']} + yields {macro['yield_trend']} → headwind for {symbol}")

    # ── 4H trend gate ──
    if t4h in ("BULLISH", "STRONG_BULLISH"):
        bull_tech.append(f"4H trend: {t4h} — multi-timeframe confirmed")
    elif t4h in ("BEARISH", "STRONG_BEARISH"):
        bear_tech.append(f"4H trend: {t4h} — multi-timeframe confirmed")

    # ── Signal decision: ≥4 total, ≥1 fundamental, 4H+1H must align ──
    bull_all = bull_tech + bull_fund
    bear_all = bear_tech + bear_fund

    direction: Optional[str] = None
    signal_reasons: list[str] = []

    if (len(bull_all) >= 4 and len(bull_fund) >= 1
            and t4h in ("BULLISH", "STRONG_BULLISH")
            and trend_1h in ("BULLISH", "NEUTRAL")
            and cur_rsi < 75):
        direction = "LONG"
        signal_reasons = bull_all

    elif (len(bear_all) >= 4 and len(bear_fund) >= 1
            and t4h in ("BEARISH", "STRONG_BEARISH")
            and trend_1h in ("BEARISH", "NEUTRAL")
            and cur_rsi > 25):
        direction = "SHORT"
        signal_reasons = bear_all

    # ── Event muting ──
    upcoming = events or get_upcoming_events(7)
    muting_event = _muted_for_symbol(symbol, upcoming)
    signal_muted = muting_event is not None
    if signal_muted:
        direction = None

    # ── Trade parameters ──
    signal: Optional[dict] = None
    if direction:
        entry = price
        atr_mult = cfg["atr_mult"]
        sl_dist = atr_mult * cur_atr

        if direction == "LONG":
            sl  = round(entry - sl_dist, 3)
            risk = entry - sl
            tp1 = round(entry + 2.0 * risk, 3)
            tp2 = round(entry + 3.0 * risk, 3)
        else:
            sl  = round(entry + sl_dist, 3)
            risk = sl - entry
            tp1 = round(entry - 2.0 * risk, 3)
            tp2 = round(entry - 3.0 * risk, 3)

        rr1 = round(abs(tp1 - entry) / risk, 1) if risk > 0 else 0
        rr2 = round(abs(tp2 - entry) / risk, 1) if risk > 0 else 0

        # Asymmetric flag — R:R ≥ 1:3 = high-conviction setup
        asymmetric = rr2 >= 3.0

        score = len(signal_reasons)
        conf_score = f"{score}/9"
        confidence_note = (
            "High conviction — 6+ factors aligned including fundamental" if score >= 6 else
            "Solid setup — 5 factors confirmed" if score >= 5 else
            "Minimum confluence met (4/9). At least 1 fundamental driver confirmed."
        )

        risk_amt = account_balance * risk_pct / 100.0
        units = round(risk_amt / risk, 4) if risk > 0 else 0

        # Seasonal alignment text
        s_align = seasonal.get("alignment", "NEUTRAL_SEASON")
        season_tag = ("✓ Aligned" if (direction == "LONG" and s_align == "BULLISH_SEASON") or
                                      (direction == "SHORT" and s_align == "BEARISH_SEASON")
                      else "✗ Conflicting" if (direction == "LONG" and s_align == "BEARISH_SEASON") or
                                              (direction == "SHORT" and s_align == "BULLISH_SEASON")
                      else "→ Neutral")

        # Upcoming event risk within 48h
        asset_events_48h = [
            e for e in get_upcoming_events(2)
            if symbol in e.get("affects", [])
        ]

        signal = {
            "direction": direction,
            "entry": round(entry, 3),
            "stop_loss": sl,
            "stop_loss_calc": f"ATR({int(atr_mult)}×ATR14): {atr_mult}×{cur_atr:.3f} = {sl_dist:.3f}",
            "take_profit_1": tp1,
            "take_profit_2": tp2,
            "risk_reward_1": rr1,
            "risk_reward_2": rr2,
            "asymmetric_setup": asymmetric,
            "timeframe": "4H trend / 1H entry",
            "confluence_score": conf_score,
            "confluence_score_num": score,
            "confluence_breakdown": {
                "technical": bull_tech if direction == "LONG" else bear_tech,
                "fundamental": bull_fund if direction == "LONG" else bear_fund,
            },
            "reasons": signal_reasons,
            "confidence_note": confidence_note,
            "seasonality_alignment": season_tag,
            "cot_summary": (
                f"MM net {cot.get('mm_net', 'N/A'):,} ({cot.get('mm_percentile', '?'):.0f}th pctile); "
                f"WoW {cot.get('wow_change_pct', 0):+.0f}%"
            ) if cot.get("available") else "COT data unavailable",
            "event_risk_48h": asset_events_48h,
            "position_size": {
                "units": units,
                "risk_amount": round(risk_amt, 2),
                "risk_pct": risk_pct,
                "account_balance": account_balance,
            },
        }

    return {
        "symbol": symbol,
        "name": cfg["name"],
        "unit": cfg["unit"],
        "price": round(price, 3),
        "trend_4h": t4h,
        "trend_1h": trend_1h,
        "indicators": {
            "ema": {
                "e9":  round(cur_e9,  3) if cur_e9  else None,
                "e21": round(cur_e21, 3) if cur_e21 else None,
                "e50": round(cur_e50, 3) if cur_e50 else None,
                "e200": round(cur_e200, 3) if cur_e200 else None,
            },
            "rsi": {"value": round(cur_rsi, 1), "divergence": rsi_div},
            "macd": {
                "line": round(cur_ml, 3), "signal_line": round(cur_ms, 3),
                "histogram": round(cur_mh, 3), "cross": macd_cross, "bullish": cur_mh > 0,
            },
            "bollinger": {
                "upper": round(cur_bbu, 3), "middle": round(cur_bbm, 3),
                "lower": round(cur_bbl, 3), "bandwidth": round(cur_bbbw, 6), "squeeze": bb_squeeze,
            },
            "vwap_24h": round(cur_vwap, 3) if cur_vwap else None,
            "volume_ratio": round(cur_volr, 2),
            "volume_spike": cur_volr >= 2.0,
            "atr": round(cur_atr, 3),
            "fibonacci": _fibonacci(df_1h, 100),
        },
        "fundamentals": {
            "cot":         cot,
            "curve":       curve,
            "seasonality": seasonal,
            "macro":       macro,
        },
        "confluence": {
            "bull_tech": bull_tech, "bull_fund": bull_fund,
            "bear_tech": bear_tech, "bear_fund": bear_fund,
            "bull_total": len(bull_tech) + len(bull_fund),
            "bear_total": len(bear_tech) + len(bear_fund),
            "active_direction": direction if not signal_muted else None,
        },
        "signal": signal,
        "signal_muted_by": muting_event,
        "generated_at": datetime.now(IST).isoformat(),
        "seasonal_note": cfg["seasonal_note"],
        "macro_driver":  cfg["macro_driver"],
        "atr_mult":      cfg["atr_mult"],
    }


def analyze_all(account_balance: float = 10_000.0, risk_pct: float = 1.0) -> dict:
    events = get_upcoming_events(7)
    results: dict[str, dict] = {}

    # Run all 4 assets in parallel — reduces total wall-clock time from
    # ~40s sequential to ~10s parallel on Railway's network.
    def _run(sym: str) -> tuple[str, dict]:
        try:
            return sym, analyze_commodity(sym, events=events,
                                          account_balance=account_balance,
                                          risk_pct=risk_pct)
        except Exception as exc:
            logger.exception("Commodity analysis failed for %s", sym)
            return sym, {"error": str(exc), "symbol": sym}

    with ThreadPoolExecutor(max_workers=4) as pool:
        futures = {pool.submit(_run, sym): sym for sym in ASSETS}
        for future in as_completed(futures, timeout=90):
            sym, data = future.result()
            results[sym] = data

    active = [s for s, r in results.items() if r.get("signal")]
    return {
        "assets": results,
        "calendar": events,
        "active_signals": active,
        "generated_at": datetime.now(IST).isoformat(),
        "disclaimer": (
            "Commodity signals are analytical tools only — not financial advice. "
            "Commodity trading involves substantial risk of loss. "
            "COT, seasonal, and macro data are educational references — always "
            "confirm with a licensed financial adviser before trading."
        ),
    }


# ══════════════════════════════════════════════════════════════════════
#  Technical Backtest (pure technical — COT/seasonal excluded)
# ══════════════════════════════════════════════════════════════════════

def backtest_commodity(symbol: str, days: int = 365,
                       account_balance: float = 10_000.0,
                       risk_pct: float = 1.0) -> dict:
    """Bar-by-bar replay of the 4H technical signal on up to 2 years of data."""
    cfg = ASSETS.get(symbol)
    if not cfg:
        return {"error": f"Unknown symbol {symbol}"}

    df = _fetch_commodity(cfg["yf_1h"], f"{min(days, 730)}d", "4h")
    if df is None or len(df) < 60:
        return {"error": f"Insufficient data for {symbol} backtest"}

    # Precompute indicators
    close = df["close"]
    e9_s  = ema(close, 9);  e21_s = ema(close, 21);  e50_s = ema(close, 50)
    rsi_s = rsi(close, 14)
    ml_s, ms_s, mh_s = macd(close, 12, 26, 9)
    bb_u_s, _, bb_l_s, _, _ = bollinger_bands(close, 20, 2.0)
    atr_s = atr(df, 14)

    equity = account_balance
    peak   = equity
    max_dd = 0.0
    trades: list[dict] = []
    pos    = None
    equity_curve: list[float] = []

    for i in range(50, len(df)):
        hi, lo = float(df["high"].iloc[i]), float(df["low"].iloc[i])
        c = float(close.iloc[i])
        a = float(atr_s.iloc[i]) if not pd.isna(atr_s.iloc[i]) else c * 0.015

        # Manage position
        if pos:
            exited, exit_p = False, None
            if pos["dir"] == "LONG":
                if lo <= pos["sl"]: exited, exit_p = True, pos["sl"]
                elif hi >= pos["tp"]: exited, exit_p = True, pos["tp"]
            else:
                if hi >= pos["sl"]: exited, exit_p = True, pos["sl"]
                elif lo <= pos["tp"]: exited, exit_p = True, pos["tp"]

            if exited:
                risk0 = abs(pos["entry"] - pos["sl0"])
                r_mult = ((exit_p - pos["entry"]) / risk0 if pos["dir"] == "LONG"
                          else (pos["entry"] - exit_p) / risk0)
                r_mult = round(r_mult, 2)
                pnl = equity * risk_pct / 100 * r_mult
                equity += pnl
                month = df.index[i].month if hasattr(df.index[i], "month") else 1
                season = ("Winter" if month in (12, 1, 2) else
                          "Spring" if month in (3, 4, 5) else
                          "Summer" if month in (6, 7, 8) else "Autumn")
                trades.append({
                    "dir": pos["dir"], "r": r_mult, "pnl": round(pnl, 2),
                    "result": "win" if pnl > 0 else "loss", "season": season,
                })
                pos = None
                peak = max(peak, equity)
                max_dd = max(max_dd, (peak - equity) / peak * 100)

        # New entry
        if pos is None:
            try:
                e9v, e21v, e50v = float(e9_s.iloc[i]), float(e21_s.iloc[i]), float(e50_s.iloc[i])
                rv = float(rsi_s.iloc[i]); mhv = float(mh_s.iloc[i])
                bbu = float(bb_u_s.iloc[i]); bbl = float(bb_l_s.iloc[i])
                if any(pd.isna(x) for x in (e9v, e21v, e50v, rv, mhv)): continue

                if e9v > e21v > e50v and mhv > 0 and 40 < rv < 70 and c > bbl:
                    sl = c - cfg["atr_mult"] * a
                    pos = {"dir": "LONG", "entry": c, "sl": sl, "sl0": sl, "tp": c + 2 * (c - sl)}
                elif e9v < e21v < e50v and mhv < 0 and 30 < rv < 60 and c < bbu:
                    sl = c + cfg["atr_mult"] * a
                    pos = {"dir": "SHORT", "entry": c, "sl": sl, "sl0": sl, "tp": c - 2 * (sl - c)}
            except Exception:
                pass

        equity_curve.append(round(equity, 2))

    wins   = [t for t in trades if t["result"] == "win"]
    losses = [t for t in trades if t["result"] == "loss"]
    n = len(trades)
    gw = sum(t["pnl"] for t in wins)
    gl = abs(sum(t["pnl"] for t in losses))

    # Season breakdown
    by_season: dict[str, dict] = {}
    for t in trades:
        s = t["season"]
        b = by_season.setdefault(s, {"trades": 0, "wins": 0, "net_r": 0.0})
        b["trades"] += 1; b["wins"] += t["result"] == "win"; b["net_r"] = round(b["net_r"] + t["r"], 2)
    for b in by_season.values():
        b["win_rate_pct"] = round(b["wins"] / b["trades"] * 100, 1)

    step = max(1, len(equity_curve) // 200)
    return {
        "symbol": symbol, "name": cfg["name"], "timeframe": "4H",
        "days_tested": days, "total_trades": n,
        "wins": len(wins), "losses": len(losses),
        "win_rate_pct": round(len(wins) / n * 100, 1) if n else 0.0,
        "avg_r": round(sum(t["r"] for t in trades) / n, 2) if n else 0.0,
        "profit_factor": round(gw / gl, 2) if gl else None,
        "net_pnl": round(equity - account_balance, 2),
        "return_pct": round((equity - account_balance) / account_balance * 100, 2),
        "max_drawdown_pct": round(max_dd, 2),
        "by_season": by_season,
        "equity_curve": equity_curve[::step],
        "note": "Technical-only backtest (EMA + RSI + MACD). COT/seasonal data not replayed — live signals use additional fundamental filters.",
    }
