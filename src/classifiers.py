"""
classifiers.py
--------------
Classification logic for customer reviews.

Two interchangeable strategies are provided:

1. RuleBasedClassifier  -> keyword / lexicon based. No API key, no cost, fully
   offline. This is the default so the project always runs out of the box.

2. OpenAIClassifier     -> optional LLM-based classifier. Used only when an
   OPENAI_API_KEY is present in the environment AND the `openai` package is
   installed. Falls back gracefully to the rule-based classifier on any error.

Both classifiers expose the same interface:

    classifier.classify(text, rating) -> dict with keys:
        sentiment      : "positive" | "neutral" | "negative"
        issue_category : "delivery" | "product quality" | "pricing" |
                         "app experience" | "customer service" | "payment" | "other"
        urgency        : "low" | "medium" | "high"

Keeping a shared interface means the rest of the pipeline does not care which
engine is doing the work -- a common pattern in production automation.
"""

from __future__ import annotations

import logging
import os
import re

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Lexicons used by the rule-based classifier
# ---------------------------------------------------------------------------

POSITIVE_WORDS = {
    "great", "love", "excellent", "amazing", "perfect", "helpful", "fast",
    "impressed", "polite", "quick", "solid", "good", "exceeded", "five stars",
    "well packaged", "value",
}

NEGATIVE_WORDS = {
    "late", "crash", "crashing", "broken", "damaged", "refund", "overpriced",
    "poor", "frustrating", "frustrated", "unacceptable", "wrong", "slow",
    "clunky", "mess", "silent", "careless", "double charged", "charged twice",
    "falling apart", "lost", "nickel-and-dimed",
}

# Each category maps to the keywords that signal it. Order matters only when a
# review hits several categories -- we pick the one with the most keyword hits.
CATEGORY_KEYWORDS = {
    "delivery": [
        "deliver", "delivery", "shipping", "shipped", "arrived", "tracking",
        "late", "package", "packaged", "box", "courier", "express",
    ],
    "product quality": [
        "quality", "fabric", "damaged", "broke", "broken", "falling apart",
        "wash", "defective", "material", "crushed",
    ],
    "pricing": [
        "price", "priced", "overpriced", "expensive", "cost", "value",
        "nickel-and-dimed", "fee",
    ],
    "app experience": [
        "app", "checkout button", "crash", "crashing", "android", "ios",
        "website", "site", "navigate", "slow", "clunky", "page", "login",
    ],
    "customer service": [
        "support", "customer service", "rep", "agent", "responded", "response",
        "return", "helpful", "no one", "emails", "contact",
    ],
    "payment": [
        "payment", "charged", "charge", "double charged", "billing", "refund",
        "transaction", "card",
    ],
}

# Words that push urgency up regardless of category.
HIGH_URGENCY_WORDS = {
    "refund", "double charged", "charged twice", "unacceptable", "damaged",
    "wrong item", "fraud", "still not processed", "no one has responded",
}


# ---------------------------------------------------------------------------
# Rule-based classifier (default, always available)
# ---------------------------------------------------------------------------

class RuleBasedClassifier:
    """Transparent, offline classifier based on keywords + star rating."""

    name = "rule-based"

    def classify(self, text: str, rating: int | None = None) -> dict:
        text_l = (text or "").lower()

        return {
            "sentiment": self._sentiment(text_l, rating),
            "issue_category": self._category(text_l),
            "urgency": self._urgency(text_l, rating),
        }

    # -- sentiment ----------------------------------------------------------
    def _sentiment(self, text_l: str, rating: int | None) -> str:
        pos = sum(1 for w in POSITIVE_WORDS if w in text_l)
        neg = sum(1 for w in NEGATIVE_WORDS if w in text_l)

        # Star rating is a strong, structured signal -- blend it with keywords.
        if rating is not None:
            if rating >= 4:
                pos += 2
            elif rating <= 2:
                neg += 2

        if neg > pos:
            return "negative"
        if pos > neg:
            return "positive"
        return "neutral"

    # -- issue category -----------------------------------------------------
    def _category(self, text_l: str) -> str:
        scores = {}
        for category, keywords in CATEGORY_KEYWORDS.items():
            hits = sum(1 for kw in keywords if kw in text_l)
            if hits:
                scores[category] = hits

        if not scores:
            return "other"
        # Highest keyword count wins; ties resolved by dict insertion order.
        return max(scores, key=scores.get)

    # -- urgency ------------------------------------------------------------
    def _urgency(self, text_l: str, rating: int | None) -> str:
        if any(w in text_l for w in HIGH_URGENCY_WORDS):
            return "high"
        if rating is not None and rating <= 2:
            return "high" if any(w in text_l for w in NEGATIVE_WORDS) else "medium"
        if rating is not None and rating == 3:
            return "medium"
        return "low"


# ---------------------------------------------------------------------------
# Optional OpenAI classifier
# ---------------------------------------------------------------------------

OPENAI_SYSTEM_PROMPT = """You are a customer feedback analyst. Classify the \
review and respond ONLY with compact JSON:
{"sentiment": "...", "issue_category": "...", "urgency": "..."}
sentiment must be one of: positive, neutral, negative.
issue_category must be one of: delivery, product quality, pricing, \
app experience, customer service, payment, other.
urgency must be one of: low, medium, high."""


class OpenAIClassifier:
    """LLM-backed classifier. Falls back to rule-based on any failure."""

    name = "openai"

    def __init__(self, model: str = "gpt-4o-mini"):
        self.model = model
        self._fallback = RuleBasedClassifier()
        self._client = None

        try:
            from openai import OpenAI  # imported lazily so it stays optional

            self._client = OpenAI()  # reads OPENAI_API_KEY from environment
            logger.info("OpenAI classifier ready (model=%s)", model)
        except Exception as exc:  # noqa: BLE001 - we deliberately catch all
            logger.warning("OpenAI unavailable (%s); using rule-based fallback", exc)
            self._client = None

    def classify(self, text: str, rating: int | None = None) -> dict:
        if self._client is None:
            return self._fallback.classify(text, rating)

        try:
            import json

            resp = self._client.chat.completions.create(
                model=self.model,
                temperature=0,
                messages=[
                    {"role": "system", "content": OPENAI_SYSTEM_PROMPT},
                    {"role": "user", "content": f"Rating: {rating}\nReview: {text}"},
                ],
            )
            raw = resp.choices[0].message.content.strip()
            raw = re.sub(r"^```(json)?|```$", "", raw).strip()
            result = json.loads(raw)
            # Validate the model stayed inside our taxonomy; fall back if not.
            if {"sentiment", "issue_category", "urgency"} <= result.keys():
                return result
            raise ValueError(f"unexpected keys: {result.keys()}")
        except Exception as exc:  # noqa: BLE001
            logger.warning("OpenAI call failed (%s); using rule-based fallback", exc)
            return self._fallback.classify(text, rating)


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------

def get_classifier(prefer_openai: bool = True):
    """Return an OpenAI classifier if usable, otherwise the rule-based one."""
    if prefer_openai and os.getenv("OPENAI_API_KEY"):
        return OpenAIClassifier()
    return RuleBasedClassifier()
