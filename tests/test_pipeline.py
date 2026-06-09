"""
Unit + smoke tests for the feedback automation pipeline.

Run with:  pytest -q
These cover the parts most likely to break silently: classifier taxonomy,
data cleaning, summary maths, and a full end-to-end run on the sample CSV.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import pytest

# Make src/ importable regardless of where pytest is invoked from.
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from classifiers import RuleBasedClassifier  # noqa: E402
from report import build_summary  # noqa: E402
from process_feedback import clean_reviews, load_reviews  # noqa: E402

VALID_SENTIMENTS = {"positive", "neutral", "negative"}
VALID_CATEGORIES = {
    "delivery", "product quality", "pricing", "app experience",
    "customer service", "payment", "other",
}
VALID_URGENCY = {"low", "medium", "high"}


# --------------------------------------------------------------------------
# Classifier
# --------------------------------------------------------------------------

@pytest.fixture
def clf():
    return RuleBasedClassifier()


def test_classifier_output_is_in_taxonomy(clf):
    result = clf.classify("My order arrived late and tracking never updated.", rating=2)
    assert result["sentiment"] in VALID_SENTIMENTS
    assert result["issue_category"] in VALID_CATEGORIES
    assert result["urgency"] in VALID_URGENCY


def test_high_rating_is_positive(clf):
    assert clf.classify("Great quality, love it!", rating=5)["sentiment"] == "positive"


def test_low_rating_complaint_is_negative(clf):
    assert clf.classify("Terrible, falling apart already.", rating=1)["sentiment"] == "negative"


def test_refund_drives_high_urgency(clf):
    assert clf.classify("Refund still not processed. Unacceptable.", rating=1)["urgency"] == "high"


def test_delivery_keyword_categorised(clf):
    assert clf.classify("Shipping was late and the package was damaged.", rating=2)[
        "issue_category"
    ] == "delivery"


def test_empty_text_does_not_crash(clf):
    result = clf.classify("", rating=None)
    assert result["sentiment"] in VALID_SENTIMENTS


# --------------------------------------------------------------------------
# Cleaning
# --------------------------------------------------------------------------

def test_clean_drops_empty_and_duplicates():
    df = pd.DataFrame(
        {
            "review_id": [1, 2, 3, 4],
            "review_text": ["good product", "good product", "   ", "bad service"],
            "rating": [5, 5, 3, 1],
        }
    )
    cleaned = clean_reviews(df)
    # Duplicate text and the whitespace-only row should be gone.
    assert len(cleaned) == 2
    assert set(cleaned["review_text"]) == {"good product", "bad service"}


def test_clean_raises_on_all_empty():
    df = pd.DataFrame({"review_id": [1], "review_text": [""]})
    with pytest.raises(ValueError):
        clean_reviews(df)


# --------------------------------------------------------------------------
# Summary
# --------------------------------------------------------------------------

def test_summary_counts_match_input():
    df = pd.DataFrame(
        {
            "review_id": [1, 2, 3],
            "date": ["2026-05-01", "2026-05-02", "2026-05-03"],
            "review_text": ["a", "b", "c"],
            "sentiment": ["negative", "positive", "negative"],
            "issue_category": ["delivery", "product quality", "delivery"],
            "urgency": ["high", "low", "high"],
        }
    )
    summary = build_summary(df)
    assert summary["total_reviews"] == 3
    assert summary["sentiment_distribution"]["negative"] == 2
    assert summary["negative_share_pct"] == pytest.approx(66.7, abs=0.1)
    assert summary["top_complaint_categories"]["delivery"] == 2


# --------------------------------------------------------------------------
# End-to-end smoke test on the bundled sample data
# --------------------------------------------------------------------------

def test_sample_csv_runs_end_to_end():
    df = load_reviews(ROOT / "data" / "sample_reviews.csv")
    df = clean_reviews(df)
    clf = RuleBasedClassifier()
    df["sentiment"] = df.apply(
        lambda r: clf.classify(r["review_text"], r.get("rating"))["sentiment"], axis=1
    )
    df["issue_category"] = df.apply(
        lambda r: clf.classify(r["review_text"], r.get("rating"))["issue_category"], axis=1
    )
    df["urgency"] = df.apply(
        lambda r: clf.classify(r["review_text"], r.get("rating"))["urgency"], axis=1
    )
    summary = build_summary(df)
    assert summary["total_reviews"] == len(df) > 0
    assert set(df["sentiment"]).issubset(VALID_SENTIMENTS)
    assert set(df["issue_category"]).issubset(VALID_CATEGORIES)
