"""
report.py
---------
Turns the classified review dataframe into a business-facing summary:

  - total reviews processed
  - sentiment distribution
  - top complaint categories
  - emerging issues (recent vs. earlier negative volume)
  - recommended actions

The summary is returned as a dict (easy to serialize to JSON for n8n / a
dashboard) and can also be rendered as a readable Markdown report.
"""

from __future__ import annotations

from collections import Counter
from datetime import datetime

import pandas as pd

# Plain-language playbook: category -> recommended business action.
ACTION_PLAYBOOK = {
    "delivery": "Audit the courier SLA and fix tracking-page updates; "
                "proactively notify customers of delays.",
    "product quality": "Open a quality review with the supplier on the flagged "
                       "SKUs; tighten incoming QA checks.",
    "pricing": "Review price perception vs. competitors; make shipping costs "
               "visible earlier in the funnel.",
    "app experience": "Prioritise the checkout/crash bugs with engineering; add "
                      "monitoring on the Android checkout flow.",
    "customer service": "Review response-time SLAs and staffing; add auto-"
                        "acknowledgement for billing tickets.",
    "payment": "Escalate double-charge/refund cases to finance immediately; "
               "audit the payment gateway for duplicate transactions.",
    "other": "Route to a human analyst for manual triage.",
}


def build_summary(df: pd.DataFrame, emerging_window: int = 5) -> dict:
    """Compute the summary metrics from a classified dataframe."""
    total = len(df)

    sentiment_dist = df["sentiment"].value_counts().to_dict()

    negatives = df[df["sentiment"] == "negative"]
    top_categories = (
        negatives["issue_category"].value_counts().head(5).to_dict()
    )

    high_urgency = int((df["urgency"] == "high").sum())

    emerging = _emerging_issues(df, emerging_window)

    recommendations = [
        {"category": cat, "complaints": count, "action": ACTION_PLAYBOOK.get(cat, ACTION_PLAYBOOK["other"])}
        for cat, count in top_categories.items()
    ]

    return {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "total_reviews": total,
        "sentiment_distribution": sentiment_dist,
        "negative_share_pct": round(100 * len(negatives) / total, 1) if total else 0.0,
        "high_urgency_count": high_urgency,
        "top_complaint_categories": top_categories,
        "emerging_issues": emerging,
        "recommended_actions": recommendations,
    }


def _emerging_issues(df: pd.DataFrame, window: int) -> list[dict]:
    """
    Naive 'emerging issue' signal: compare the complaint mix in the most recent
    `window` reviews against everything before it. Categories that appear more
    often in the recent slice are flagged as emerging.
    """
    if "date" not in df.columns or len(df) <= window:
        return []

    ordered = df.sort_values("date")
    recent = ordered.tail(window)
    earlier = ordered.head(len(ordered) - window)

    recent_neg = Counter(
        recent[recent["sentiment"] == "negative"]["issue_category"]
    )
    earlier_neg = Counter(
        earlier[earlier["sentiment"] == "negative"]["issue_category"]
    )

    emerging = []
    for category, recent_count in recent_neg.items():
        earlier_count = earlier_neg.get(category, 0)
        if recent_count > earlier_count:
            emerging.append(
                {
                    "category": category,
                    "recent_negative": recent_count,
                    "earlier_negative": earlier_count,
                }
            )
    emerging.sort(key=lambda x: x["recent_negative"], reverse=True)
    return emerging


def render_markdown(summary: dict) -> str:
    """Render the summary dict as a human-readable Markdown report."""
    lines = [
        "# Customer Feedback Summary Report",
        f"_Generated: {summary['generated_at']}_",
        "",
        f"**Total reviews processed:** {summary['total_reviews']}",
        f"**Negative share:** {summary['negative_share_pct']}%",
        f"**High-urgency reviews:** {summary['high_urgency_count']}",
        "",
        "## Sentiment distribution",
    ]
    for sentiment, count in summary["sentiment_distribution"].items():
        lines.append(f"- {sentiment}: {count}")

    lines += ["", "## Top complaint categories"]
    if summary["top_complaint_categories"]:
        for cat, count in summary["top_complaint_categories"].items():
            lines.append(f"- {cat}: {count}")
    else:
        lines.append("- No negative reviews detected.")

    lines += ["", "## Emerging issues"]
    if summary["emerging_issues"]:
        for item in summary["emerging_issues"]:
            lines.append(
                f"- **{item['category']}** rising "
                f"({item['earlier_negative']} -> {item['recent_negative']} negative)"
            )
    else:
        lines.append("- None detected in the recent window.")

    lines += ["", "## Recommended actions"]
    for rec in summary["recommended_actions"]:
        lines.append(
            f"- **{rec['category']}** ({rec['complaints']} complaints): {rec['action']}"
        )

    return "\n".join(lines) + "\n"
