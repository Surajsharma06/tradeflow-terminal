"""
Signal scoring system.

Combines technical, sentiment, volume, regime, and macro sub-scores
into a single composite score (0 – 100) that drives trade / no-trade
decisions and position-size conviction adjustments.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Optional

logger = logging.getLogger(__name__)


@dataclass
class ScoreBreakdown:
    """Detailed breakdown of a signal's composite score."""

    technical: float = 0.0   # 0 – 40
    sentiment: float = 0.0   # 0 – 20
    volume: float = 0.0      # 0 – 15
    regime: float = 0.0      # 0 – 15
    macro: float = 0.0       # 0 – 10
    total: float = 0.0       # 0 – 100
    details: dict[str, Any] = field(default_factory=dict)


class SignalScorer:
    """Multi-factor signal scoring engine.

    Sub-score allocation
    --------------------
    | Factor     | Max  | Weight |
    |------------|------|--------|
    | Technical  |  40  |  40 %  |
    | Sentiment  |  20  |  20 %  |
    | Volume     |  15  |  15 %  |
    | Regime     |  15  |  15 %  |
    | Macro      |  10  |  10 %  |
    """

    # ── Constructor ──────────────────────────────────────────────────

    def __init__(
        self,
        conviction_threshold: float = 75.0,
        high_conviction_threshold: float = 85.0,
    ) -> None:
        self._conviction_threshold = conviction_threshold
        self._high_conviction_threshold = high_conviction_threshold

    # ── Public API ───────────────────────────────────────────────────

    def score_signal(
        self,
        signal: dict[str, Any],
        indicators: Optional[dict[str, Any]] = None,
        sentiment: Optional[dict[str, Any]] = None,
        volume_data: Optional[dict[str, Any]] = None,
        regime: Optional[str] = None,
        macro: Optional[dict[str, Any]] = None,
    ) -> ScoreBreakdown:
        """Compute a composite score for *signal*.

        Parameters
        ----------
        signal : dict
            Must contain at least ``direction`` and ``strategy_name``.
        indicators : dict, optional
            Technical indicator values (``rsi``, ``adx``, ``macd_histogram``,
            ``supertrend_direction``, ``ema_trend_aligned``).
        sentiment : dict, optional
            Sentiment data (``news_score``, ``social_score`` each −1 … 1).
        volume_data : dict, optional
            Volume metrics (``volume_ratio``, ``delivery_pct``,
            ``oi_buildup``).
        regime : str, optional
            Current market regime name (from :class:`MarketRegime`).
        macro : dict, optional
            Macro data (``vix``, ``fii_net``, ``global_cue``).

        Returns
        -------
        ScoreBreakdown
        """
        direction = signal.get("direction", "BUY")
        tech = self._technical_score(indicators or {}, direction)
        sent = self._sentiment_score(sentiment or {}, direction)
        vol = self._volume_score(volume_data or {})
        reg = self._regime_score(signal.get("strategy_name", ""), regime, direction)
        mac = self._macro_score(macro or {})

        total = tech + sent + vol + reg + mac
        total = max(0.0, min(100.0, total))

        breakdown = ScoreBreakdown(
            technical=round(tech, 1),
            sentiment=round(sent, 1),
            volume=round(vol, 1),
            regime=round(reg, 1),
            macro=round(mac, 1),
            total=round(total, 1),
            details={
                "signal_direction": signal.get("direction"),
                "strategy": signal.get("strategy_name"),
                "regime": regime,
            },
        )
        logger.info(
            "Signal scored: total=%.1f (tech=%.1f, sent=%.1f, vol=%.1f, "
            "regime=%.1f, macro=%.1f) for %s/%s",
            total, tech, sent, vol, reg, mac,
            signal.get("strategy_name"),
            signal.get("direction"),
        )
        return breakdown

    # ── Sub-scoring methods ──────────────────────────────────────────

    def _technical_score(self, indicators: dict[str, Any], direction: str = "BUY") -> float:
        """Score technical indicator alignment (0 – 40), direction-aware.

        Factors
        -------
        - RSI in favourable zone          (0 – 10)
        - ADX > 25 (trend strength)       (0 – 8)
        - MACD histogram confirms signal  (0 – 8)
        - Supertrend direction aligned     (0 – 7)
        - EMA trend alignment             (0 – 7)
        """
        score = 0.0
        is_buy = direction == "BUY"

        # RSI (0 – 10) — direction-aware
        rsi_val = indicators.get("rsi")
        if rsi_val is not None:
            if is_buy:
                # BUY: best when oversold recovering (30–55), still OK up to 65
                if 30 <= rsi_val <= 55:
                    score += 10.0
                elif 55 < rsi_val <= 65:
                    score += 6.0
                elif 20 <= rsi_val < 30:
                    score += 4.0  # extreme oversold — risky but possible
                else:
                    score += 1.0  # overbought → bad for BUY
            else:
                # SELL: best when overbought falling (45–70), still OK down to 35
                if 45 <= rsi_val <= 70:
                    score += 10.0
                elif 35 <= rsi_val < 45:
                    score += 6.0
                elif 70 < rsi_val <= 80:
                    score += 4.0  # extreme overbought — risky but possible
                else:
                    score += 1.0  # oversold → bad for SELL

        # ADX (0 – 8) — same for both directions
        # ADX < 20 = sideways market: return 0 immediately (hard gate)
        adx_val = indicators.get("adx")
        if adx_val is not None:
            if adx_val < 20:
                return 0.0   # sideways market — no technical edge
            if adx_val > 30:
                score += 8.0
            elif adx_val > 25:
                score += 6.0
            else:
                score += 3.0  # 20–25: weak trend

        # MACD histogram (0 – 8) — direction-aware
        hist = indicators.get("macd_histogram")
        if hist is not None:
            if is_buy:
                if hist > 0:
                    score += 8.0
                elif hist > -0.5:
                    score += 4.0
            else:
                if hist < 0:
                    score += 8.0
                elif hist < 0.5:
                    score += 4.0

        # Supertrend direction (0 – 7) — direction-aware
        st_dir = indicators.get("supertrend_direction")
        if st_dir is not None:
            if (is_buy and st_dir == 1) or (not is_buy and st_dir == -1):
                score += 7.0
            else:
                score += 1.0  # counter-trend → penalise

        # EMA trend aligned (0 – 7)
        ema_aligned = indicators.get("ema_trend_aligned")
        if ema_aligned is True:
            score += 7.0
        elif ema_aligned is False:
            score += 1.0

        return min(40.0, score)

    def _sentiment_score(self, sentiment_data: dict[str, Any], direction: str = "BUY") -> float:
        """Score news and social sentiment (0 – 20), direction-aware.

        Expects ``news_score`` and ``social_score`` in [−1, 1].
        Positive sentiment boosts BUY; negative sentiment boosts SELL.
        """
        score = 0.0
        flip = 1.0 if direction == "BUY" else -1.0

        # News (0 – 12): aligned sentiment gets full marks, opposing gets 0
        news = sentiment_data.get("news_score")
        if news is not None:
            aligned_news = (news * flip + 1) / 2  # remap so aligned=1, opposing=0
            score += max(0.0, aligned_news * 12.0)

        # Social (0 – 8)
        social = sentiment_data.get("social_score")
        if social is not None:
            aligned_social = (social * flip + 1) / 2
            score += max(0.0, aligned_social * 8.0)

        # Default baseline when no data
        if news is None and social is None:
            score = 10.0  # neutral

        return min(20.0, score)

    def _volume_score(self, volume_data: dict[str, Any]) -> float:
        """Score volume confirmation (0 – 15).

        Factors
        -------
        - Relative volume > 1       (0 – 6)
        - Delivery % > 50           (0 – 5)
        - OI build-up confirmation   (0 – 4)
        """
        score = 0.0

        vol_ratio = volume_data.get("volume_ratio")
        if vol_ratio is not None:
            if vol_ratio > 2.0:
                score += 6.0
            elif vol_ratio > 1.5:
                score += 4.0
            elif vol_ratio > 1.0:
                score += 2.0

        delivery = volume_data.get("delivery_pct")
        if delivery is not None:
            if delivery > 60:
                score += 5.0
            elif delivery > 50:
                score += 3.0
            elif delivery > 40:
                score += 1.0

        oi = volume_data.get("oi_buildup")
        if oi is not None:
            if oi in ("LONG_BUILDUP", "SHORT_COVERING"):
                score += 4.0
            elif oi == "NO_CHANGE":
                score += 2.0
            # SHORT_BUILDUP / LONG_UNWINDING → 0

        # Default baseline
        if vol_ratio is None and delivery is None and oi is None:
            score = 7.5

        return min(15.0, score)

    def _regime_score(
        self,
        strategy_name: str,
        current_regime: Optional[str],
        direction: str = "BUY",
    ) -> float:
        """Score strategy–regime fitness (0 – 15), direction-aware.

        Penalises signals that fight the dominant regime direction.
        """
        if current_regime is None:
            return 7.5  # neutral when unknown

        # Hard penalty: BUY in BEAR or SELL in BULL reduces max score to 5
        regime_direction_conflict = (
            (direction == "BUY" and current_regime == "BEAR_TRENDING") or
            (direction == "SELL" and current_regime == "BULL_TRENDING")
        )
        max_regime_score = 5.0 if regime_direction_conflict else 15.0

        fit_map: dict[str, set[str]] = {
            "BULL_TRENDING": {
                "trend_following", "momentum_breakout", "swing",
                "momentum", "breakout", "ema_crossover",
            },
            "BEAR_TRENDING": {
                "mean_reversion", "pair_trading", "options",
                "support_resistance",
            },
            "SIDEWAYS": {
                "mean_reversion", "scalping", "bollinger_squeeze",
                "pair_trading", "options", "support_resistance",
            },
            "HIGH_VOLATILITY": {
                "scalping", "mean_reversion", "options",
            },
            "LOW_VOLATILITY": {
                "trend_following", "momentum", "breakout",
                "swing", "momentum_breakout",
            },
        }

        suitable = fit_map.get(current_regime, set())
        if strategy_name in suitable:
            raw = 15.0
        elif strategy_name in {"trend_following", "mean_reversion", "swing"}:
            raw = 8.0
        else:
            raw = 3.0

        return min(max_regime_score, raw)

    def _macro_score(self, macro_data: dict[str, Any]) -> float:
        """Score macro / global conditions (0 – 10).

        Factors
        -------
        - VIX level            (0 – 4)
        - FII net flow         (0 – 3)
        - Global cues aligned  (0 – 3)
        """
        score = 0.0

        vix = macro_data.get("vix")
        if vix is not None:
            if vix < 15:
                score += 4.0
            elif vix < 20:
                score += 3.0
            elif vix < 25:
                score += 1.0
            # vix >= 25 → 0

        fii_net = macro_data.get("fii_net")
        if fii_net is not None:
            if fii_net > 500_000_000:  # ₹50 Cr net buy
                score += 3.0
            elif fii_net > 0:
                score += 2.0
            elif fii_net > -500_000_000:
                score += 1.0

        global_cue = macro_data.get("global_cue")
        if global_cue is not None:
            if global_cue == "POSITIVE":
                score += 3.0
            elif global_cue == "NEUTRAL":
                score += 1.5

        # Default baseline
        if vix is None and fii_net is None and global_cue is None:
            score = 5.0

        return min(10.0, score)

    # ── Decision helpers ─────────────────────────────────────────────

    def should_trade(
        self,
        total_score: float,
        conviction_threshold: Optional[float] = None,
    ) -> bool:
        """Return ``True`` if *total_score* meets the conviction bar.

        Parameters
        ----------
        total_score : float
            Composite score (0 – 100).
        conviction_threshold : float, optional
            Override the default threshold (72).
        """
        threshold = conviction_threshold or self._conviction_threshold
        result = total_score >= threshold
        logger.debug(
            "should_trade: score=%.1f, threshold=%.1f → %s",
            total_score,
            threshold,
            result,
        )
        return result

    def is_high_conviction(
        self,
        total_score: float,
        threshold: Optional[float] = None,
    ) -> bool:
        """Return ``True`` if *total_score* qualifies as high conviction.

        High-conviction signals may receive larger position sizes.

        Parameters
        ----------
        total_score : float
        threshold : float, optional
            Override the default high-conviction threshold (85).
        """
        t = threshold or self._high_conviction_threshold
        return total_score >= t
