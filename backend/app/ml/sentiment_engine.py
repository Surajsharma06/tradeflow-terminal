"""
Financial sentiment analysis engine using FinBERT.

Provides text-level and batch sentiment analysis for trading signals.
Uses lazy model loading (loads on first call) to avoid slow startup.
Falls back to mock results when ``transformers`` / ``torch`` are
unavailable.
"""

import logging
from datetime import datetime
from typing import Any, Optional

import numpy as np

try:
    from transformers import AutoModelForSequenceClassification, AutoTokenizer, pipeline

    HAS_TRANSFORMERS = True
except ImportError:
    HAS_TRANSFORMERS = False

from app.core.config import get_settings

logger = logging.getLogger(__name__)

# FinBERT label mapping
_LABEL_MAP: dict[str, str] = {
    "positive": "bullish",
    "negative": "bearish",
    "neutral": "neutral",
    # ProsusAI/finbert uses these labels:
    "Positive": "bullish",
    "Negative": "bearish",
    "Neutral": "neutral",
}


class SentimentEngine:
    """
    Financial sentiment analysis using FinBERT.

    Features:
    * **Lazy loading** — the model is downloaded / loaded on the first
      call to ``analyze_text`` or ``analyze_news_batch``.
    * **Batch processing** — analyse multiple headlines efficiently.
    * **Aggregate scoring** — compute weighted sentiment for a basket
      of articles.
    * **Mock fallback** — returns random plausible sentiments when
      ``transformers`` is not installed.
    """

    def __init__(self, model_name: Optional[str] = None) -> None:
        """
        Args:
            model_name: HuggingFace model ID. Defaults to the value
                configured in ``Settings.sentiment_model``.
        """
        settings = get_settings()
        self._model_name = model_name or settings.sentiment_model
        self._pipeline: Any = None
        self._loaded: bool = False

        if not HAS_TRANSFORMERS:
            logger.info(
                "transformers not installed — "
                "SentimentEngine will return mock results"
            )
        else:
            logger.info(
                "SentimentEngine initialised (model=%s, lazy-load)",
                self._model_name,
            )

    # ── Lazy model loading ───────────────────────────────────────────

    def _ensure_loaded(self) -> bool:
        """Load the model on first use. Returns ``True`` if ready."""
        if self._loaded and self._pipeline is not None:
            return True

        if not HAS_TRANSFORMERS:
            return False

        try:
            logger.info("Loading sentiment model: %s …", self._model_name)
            self._pipeline = pipeline(
                "text-classification",
                model=self._model_name,
                tokenizer=self._model_name,
                top_k=None,  # Return all class probabilities
                truncation=True,
                max_length=512,
            )
            self._loaded = True
            logger.info("Sentiment model loaded successfully")
            return True
        except Exception as exc:
            logger.error("Failed to load sentiment model: %s", exc)
            return False

    # ── Single text analysis ─────────────────────────────────────────

    def analyze_text(self, text: str) -> dict[str, Any]:
        """
        Analyse the sentiment of a single text string.

        Args:
            text: Headline, article, or tweet text.

        Returns:
            Dict with ``sentiment`` (bullish/bearish/neutral),
            ``score``, ``probabilities``, ``model``.
        """
        if not self._ensure_loaded():
            return self._mock_analyze(text)

        try:
            results = self._pipeline(text[:512])
            # pipeline with top_k=None returns list of lists
            scores = results[0] if results else []

            prob_map: dict[str, float] = {}
            for item in scores:
                label = _LABEL_MAP.get(item["label"], item["label"].lower())
                prob_map[label] = round(float(item["score"]), 4)

            # Determine dominant sentiment
            sentiment = max(prob_map, key=prob_map.get)  # type: ignore[arg-type]
            score = self._compute_score(prob_map)

            return {
                "text": text[:100],
                "sentiment": sentiment,
                "score": score,
                "probabilities": prob_map,
                "model": self._model_name,
                "timestamp": datetime.utcnow().isoformat(),
            }

        except Exception as exc:
            logger.error("Sentiment analysis failed: %s", exc)
            return self._mock_analyze(text)

    # ── Batch analysis ───────────────────────────────────────────────

    def analyze_news_batch(
        self,
        texts: list[str],
        batch_size: int = 16,
    ) -> list[dict[str, Any]]:
        """
        Analyse sentiment for a batch of texts.

        Args:
            texts: List of headline / article strings.
            batch_size: Processing batch size.

        Returns:
            List of sentiment result dicts.
        """
        if not texts:
            return []

        if not self._ensure_loaded():
            return [self._mock_analyze(t) for t in texts]

        try:
            truncated = [t[:512] for t in texts]
            results = self._pipeline(truncated, batch_size=batch_size)

            output: list[dict[str, Any]] = []
            for text, result in zip(texts, results):
                prob_map: dict[str, float] = {}
                for item in result:
                    label = _LABEL_MAP.get(item["label"], item["label"].lower())
                    prob_map[label] = round(float(item["score"]), 4)

                sentiment = max(prob_map, key=prob_map.get)  # type: ignore[arg-type]
                score = self._compute_score(prob_map)

                output.append({
                    "text": text[:100],
                    "sentiment": sentiment,
                    "score": score,
                    "probabilities": prob_map,
                })

            logger.info("Batch sentiment: %d texts analysed", len(output))
            return output

        except Exception as exc:
            logger.error("Batch sentiment analysis failed: %s", exc)
            return [self._mock_analyze(t) for t in texts]

    # ── Aggregate sentiment ──────────────────────────────────────────

    def get_aggregate_sentiment(
        self,
        texts: list[str],
        weights: Optional[list[float]] = None,
    ) -> dict[str, Any]:
        """
        Compute a weighted aggregate sentiment across multiple texts.

        Args:
            texts: List of text strings.
            weights: Optional per-text importance weights.
                     Defaults to equal weighting.

        Returns:
            Dict with ``overall_sentiment``, ``overall_score``,
            ``bullish_pct``, ``bearish_pct``, ``neutral_pct``,
            ``count``.
        """
        if not texts:
            return {
                "overall_sentiment": "neutral",
                "overall_score": 50.0,
                "bullish_pct": 0.0,
                "bearish_pct": 0.0,
                "neutral_pct": 100.0,
                "count": 0,
            }

        results = self.analyze_news_batch(texts)

        if weights is None:
            weights = [1.0] * len(results)
        total_w = sum(weights)

        weighted_score = 0.0
        sentiments = {"bullish": 0.0, "bearish": 0.0, "neutral": 0.0}

        for result, w in zip(results, weights):
            weighted_score += result["score"] * w
            sentiments[result["sentiment"]] += w

        avg_score = weighted_score / total_w if total_w else 50.0

        if avg_score >= 60:
            overall = "bullish"
        elif avg_score <= 40:
            overall = "bearish"
        else:
            overall = "neutral"

        return {
            "overall_sentiment": overall,
            "overall_score": round(avg_score, 2),
            "bullish_pct": round(sentiments["bullish"] / total_w * 100, 1),
            "bearish_pct": round(sentiments["bearish"] / total_w * 100, 1),
            "neutral_pct": round(sentiments["neutral"] / total_w * 100, 1),
            "count": len(results),
            "timestamp": datetime.utcnow().isoformat(),
        }

    # ── Market sentiment ─────────────────────────────────────────────

    def get_market_sentiment(
        self,
        headlines: list[str],
    ) -> dict[str, Any]:
        """
        Convenience method: compute market-level sentiment from headlines.

        Equivalent to ``get_aggregate_sentiment`` with equal weights,
        plus a human-readable description.
        """
        agg = self.get_aggregate_sentiment(headlines)

        score = agg["overall_score"]
        if score >= 75:
            desc = "Strongly bullish market sentiment"
        elif score >= 60:
            desc = "Moderately bullish market sentiment"
        elif score >= 40:
            desc = "Neutral market sentiment"
        elif score >= 25:
            desc = "Moderately bearish market sentiment"
        else:
            desc = "Strongly bearish market sentiment"

        agg["description"] = desc
        return agg

    # ── Score helpers ────────────────────────────────────────────────

    @staticmethod
    def _compute_score(prob_map: dict[str, float]) -> float:
        """
        Convert sentiment probabilities to a 0–100 score.

        * 100 = extremely bullish
        * 50 = neutral
        * 0 = extremely bearish
        """
        bullish = prob_map.get("bullish", 0.0)
        bearish = prob_map.get("bearish", 0.0)
        # Normalised directional score
        score = 50 + (bullish - bearish) * 50
        return round(max(0, min(100, score)), 2)

    # ── Mock fallback ────────────────────────────────────────────────

    @staticmethod
    def _mock_analyze(text: str) -> dict[str, Any]:
        """Return a plausible mock sentiment result."""
        probs = np.random.dirichlet([3, 3, 4])
        labels = ["bearish", "neutral", "bullish"]
        prob_map = {l: round(float(p), 4) for l, p in zip(labels, probs)}
        sentiment = max(prob_map, key=prob_map.get)  # type: ignore[arg-type]

        score = 50 + (prob_map.get("bullish", 0) - prob_map.get("bearish", 0)) * 50

        return {
            "text": text[:100],
            "sentiment": sentiment,
            "score": round(score, 2),
            "probabilities": prob_map,
            "model": "mock",
            "mock": True,
            "timestamp": datetime.utcnow().isoformat(),
        }
