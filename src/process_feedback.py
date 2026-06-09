"""
process_feedback.py
-------------------
Main entry point for the AI-Powered Customer Feedback Automation Workflow.

Pipeline:
    1. Load reviews from a CSV (or a path passed in by n8n / the CLI).
    2. Clean and validate the data.
    3. Classify each review (sentiment / issue category / urgency).
    4. Build a business summary + recommendations.
    5. Write three outputs:
         - classified reviews CSV   (dashboard-ready, e.g. Power BI / Sheets)
         - summary JSON             (machine-readable, e.g. for n8n / API)
         - summary Markdown report  (human-readable)

Designed to be run either standalone:

    python src/process_feedback.py --input data/sample_reviews.csv

or invoked by an n8n "Execute Command" node (see n8n/README in the n8n folder).

Exit codes:
    0  success
    1  recoverable/usage error (bad input, empty file)
    2  unexpected failure
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

import pandas as pd

# Allow running both as "python src/process_feedback.py" and as a module.
sys.path.insert(0, str(Path(__file__).resolve().parent))

from classifiers import get_classifier  # noqa: E402
from report import build_summary, render_markdown  # noqa: E402

REQUIRED_COLUMNS = {"review_id", "review_text"}


# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

def setup_logging(log_dir: Path) -> None:
    log_dir.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)-7s | %(message)s",
        handlers=[
            logging.FileHandler(log_dir / "run.log", encoding="utf-8"),
            logging.StreamHandler(sys.stdout),
        ],
    )


logger = logging.getLogger("process_feedback")


# ---------------------------------------------------------------------------
# Data loading & cleaning
# ---------------------------------------------------------------------------

def load_reviews(input_path: Path) -> pd.DataFrame:
    if not input_path.exists():
        raise FileNotFoundError(f"Input file not found: {input_path}")

    df = pd.read_csv(input_path)
    logger.info("Loaded %d rows from %s", len(df), input_path)

    missing = REQUIRED_COLUMNS - set(df.columns)
    if missing:
        raise ValueError(f"Input CSV is missing required columns: {missing}")

    return df


def clean_reviews(df: pd.DataFrame) -> pd.DataFrame:
    start = len(df)

    # Drop rows with no review text and trim whitespace.
    df = df.copy()
    df["review_text"] = df["review_text"].astype(str).str.strip()
    df = df[df["review_text"].str.len() > 0]
    df = df[df["review_text"].str.lower() != "nan"]

    # Remove exact duplicate reviews (same id or same text).
    df = df.drop_duplicates(subset=["review_id"])
    df = df.drop_duplicates(subset=["review_text"])

    # Normalise rating to a nullable integer if present.
    if "rating" in df.columns:
        df["rating"] = pd.to_numeric(df["rating"], errors="coerce").astype("Int64")

    dropped = start - len(df)
    if dropped:
        logger.info("Cleaning removed %d invalid/duplicate rows", dropped)

    if df.empty:
        raise ValueError("No valid reviews left after cleaning.")

    return df.reset_index(drop=True)


# ---------------------------------------------------------------------------
# Classification
# ---------------------------------------------------------------------------

def classify_reviews(df: pd.DataFrame, prefer_openai: bool) -> pd.DataFrame:
    classifier = get_classifier(prefer_openai=prefer_openai)
    logger.info("Classifying with engine: %s", classifier.name)

    sentiments, categories, urgencies = [], [], []
    for row in df.itertuples(index=False):
        text = getattr(row, "review_text", "")
        rating = getattr(row, "rating", None)
        rating = int(rating) if pd.notna(rating) else None

        result = classifier.classify(text, rating)
        sentiments.append(result["sentiment"])
        categories.append(result["issue_category"])
        urgencies.append(result["urgency"])

    df = df.copy()
    df["sentiment"] = sentiments
    df["issue_category"] = categories
    df["urgency"] = urgencies
    return df


# ---------------------------------------------------------------------------
# Output
# ---------------------------------------------------------------------------

def write_outputs(df: pd.DataFrame, summary: dict, output_dir: Path) -> dict:
    output_dir.mkdir(parents=True, exist_ok=True)

    classified_csv = output_dir / "classified_reviews.csv"
    summary_json = output_dir / "summary.json"
    summary_md = output_dir / "summary_report.md"

    df.to_csv(classified_csv, index=False, encoding="utf-8")
    summary_json.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    summary_md.write_text(render_markdown(summary), encoding="utf-8")

    logger.info("Wrote %s", classified_csv)
    logger.info("Wrote %s", summary_json)
    logger.info("Wrote %s", summary_md)

    return {
        "classified_csv": str(classified_csv),
        "summary_json": str(summary_json),
        "summary_md": str(summary_md),
    }


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def parse_args(argv=None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Customer feedback automation pipeline")
    parser.add_argument(
        "--input", "-i",
        default="data/sample_reviews.csv",
        help="Path to the input reviews CSV.",
    )
    parser.add_argument(
        "--output-dir", "-o",
        default="data/output",
        help="Directory for output files.",
    )
    parser.add_argument(
        "--log-dir",
        default="logs",
        help="Directory for log files.",
    )
    parser.add_argument(
        "--no-openai",
        action="store_true",
        help="Force the offline rule-based classifier even if an API key is set.",
    )
    return parser.parse_args(argv)


def main(argv=None) -> int:
    args = parse_args(argv)
    setup_logging(Path(args.log_dir))

    try:
        df = load_reviews(Path(args.input))
        df = clean_reviews(df)
        df = classify_reviews(df, prefer_openai=not args.no_openai)
        summary = build_summary(df)
        paths = write_outputs(df, summary, Path(args.output_dir))

        logger.info(
            "Done. %d reviews | negative %.1f%% | %d high-urgency",
            summary["total_reviews"],
            summary["negative_share_pct"],
            summary["high_urgency_count"],
        )
        # Print a compact JSON line so n8n can capture structured output.
        print(json.dumps({"status": "ok", "summary": summary, "outputs": paths}))
        return 0

    except (FileNotFoundError, ValueError) as exc:
        logger.error("Input error: %s", exc)
        print(json.dumps({"status": "error", "message": str(exc)}))
        return 1
    except Exception as exc:  # noqa: BLE001
        logger.exception("Unexpected failure")
        print(json.dumps({"status": "error", "message": str(exc)}))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
