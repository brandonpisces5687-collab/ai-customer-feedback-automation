# AI-Powered Customer Feedback Automation Workflow

[![CI](https://github.com/brandonpisces5687-collab/ai-customer-feedback-automation/actions/workflows/ci.yml/badge.svg)](https://github.com/brandonpisces5687-collab/ai-customer-feedback-automation/actions/workflows/ci.yml)

> Turn a pile of raw customer reviews into a prioritised, business-ready action
> list — automatically, on a schedule, with no manual tagging.

An end-to-end automation that ingests customer feedback (CSV / Google Sheet),
classifies each review with Python, and produces a summary report plus
recommended actions. Orchestrated with **n8n** so it can run on demand or on a
daily schedule.

This project bridges a **customer-insights / VOC analytics** background into
**AI automation engineering**: same business problem (understanding the voice of
the customer), now solved as a repeatable, monitored, documented pipeline.

---

## Screenshots

<!--
  Add three images to docs/screenshots/ (see docs/screenshots/README.md for a
  capture guide), then uncomment the lines below. Until the files exist they are
  intentionally commented out so the README shows no broken images.

  ![n8n workflow](docs/screenshots/n8n_workflow.png)
  ![Summary report](docs/screenshots/summary_report.png)
  ![Power BI dashboard](docs/screenshots/powerbi_dashboard.png)
-->

> 📸 Screenshots pending — see [`docs/screenshots/README.md`](docs/screenshots/README.md)
> for exactly what to capture (n8n canvas, summary report, Power BI dashboard).

---

## 1. Business problem

Support and CX teams receive hundreds of reviews across the app, web, and email.
Reading and tagging them by hand is slow, inconsistent, and doesn't scale — so
emerging issues (a payment bug, a delivery SLA slip) get noticed late.

**This workflow answers four questions automatically, every day:**
1. How do customers feel right now? (sentiment distribution)
2. What are they complaining about most? (issue categories)
3. What's getting *worse*? (emerging issues)
4. What should we do about it? (recommended actions per category)

---

## 2. Architecture

```
            ┌─────────────┐
 Input CSV  │    n8n      │   Manual trigger OR daily schedule
 / Sheet ──▶│  Orchestrator│
            └──────┬──────┘
                   │ Execute Command
                   ▼
        ┌───────────────────────┐
        │  Python pipeline       │
        │  process_feedback.py   │
        │                        │
        │  load → clean →        │
        │  classify → summarise  │
        └──────────┬─────────────┘
                   │
       ┌───────────┼─────────────┐
       ▼           ▼             ▼
 classified   summary.json   summary_report.md
 _reviews.csv (for n8n /     (human-readable)
 (dashboard)  API / Sheets)
```

**Classification engine is pluggable:**
- **Rule-based** (default) — keyword + star-rating lexicon. Offline, free, fully
  transparent. Runs out of the box.
- **OpenAI LLM** (optional) — set `OPENAI_API_KEY` to upgrade. Falls back to the
  rule-based engine automatically on any error or missing key.

---

## 3. Workflow steps

1. **Trigger** — n8n Manual Trigger (demo) or Schedule Trigger (daily).
2. **Run pipeline** — n8n Execute Command node calls `process_feedback.py`.
3. **Load & clean** — read CSV, drop empty/duplicate rows, normalise ratings.
4. **Classify** — each review tagged with sentiment, issue category, urgency.
5. **Summarise** — totals, sentiment distribution, top complaints, emerging
   issues, recommended actions.
6. **Export** — three files written to `data/output/`.
7. **Branch & notify** — n8n parses the pipeline's JSON output and routes to a
   success or failure notification (email / Slack / Sheets — placeholder nodes
   included).

---

## 4. Tools used

| Area | Tool |
|------|------|
| Orchestration / automation | n8n (free, self-hosted) |
| Data processing | Python 3.12, pandas |
| Classification | Rule-based lexicon (default) or OpenAI API (optional) |
| Output / dashboards | CSV (Power BI / Excel / Google Sheets ready), JSON, Markdown |
| Logging & monitoring | Python `logging` → `logs/run.log` + console |

---

## 5. Classification taxonomy

| Dimension | Values |
|-----------|--------|
| Sentiment | positive · neutral · negative |
| Issue category | delivery · product quality · pricing · app experience · customer service · payment · other |
| Urgency | low · medium · high |

---

## 6. Quick start

```bash
# 1. (optional) create a virtual environment
python -m venv .venv && .venv\Scripts\activate     # Windows
# source .venv/bin/activate                         # macOS / Linux

# 2. install dependencies
pip install -r requirements.txt

# 3. run the pipeline on the sample data
python src/process_feedback.py --input data/sample_reviews.csv

# 4. view results
#    data/output/classified_reviews.csv
#    data/output/summary.json
#    data/output/summary_report.md
```

Force the offline engine even if a key is set: add `--no-openai`.
To run via n8n instead, see [`n8n/README.md`](n8n/README.md).

---

## 7. Sample input / output

**Input** (`data/sample_reviews.csv`):

| review_id | date | rating | channel | review_text |
|-----------|------|--------|---------|-------------|
| 1001 | 2026-05-01 | 2 | app | "My order arrived three days late and the tracking page never updated." |
| 1002 | 2026-05-01 | 5 | web | "Great quality jacket, exactly as described. Will buy again!" |

**Output** (`data/output/classified_reviews.csv`):

| review_id | rating | review_text | sentiment | issue_category | urgency |
|-----------|--------|-------------|-----------|----------------|---------|
| 1001 | 2 | "...arrived three days late..." | negative | delivery | high |
| 1002 | 5 | "Great quality jacket..." | positive | product quality | low |

**Output** (`data/output/summary_report.md`) — abridged:

```
# Customer Feedback Summary Report
Total reviews processed: 20
Negative share: 65.0%
High-urgency reviews: 11

## Top complaint categories
- delivery: 4
- app experience: 2
- payment: 2

## Emerging issues
- payment rising (0 -> 2 negative)

## Recommended actions
- delivery (4 complaints): Audit the courier SLA and fix tracking-page updates...
- payment (2 complaints): Escalate double-charge/refund cases to finance immediately...
```

---

## 8. Project structure

```
AI-Powered Customer Feedback Automation Workflow/
├── README.md                     # this file
├── requirements.txt
├── .gitignore
├── data/
│   ├── sample_reviews.csv         # sample input
│   └── output/                    # generated results (git-ignored)
├── src/
│   ├── process_feedback.py        # main pipeline / CLI entry point
│   ├── classifiers.py             # rule-based + optional OpenAI classifiers
│   └── report.py                  # summary metrics + Markdown rendering
├── n8n/
│   ├── feedback_automation_workflow.json   # importable n8n workflow
│   └── README.md                  # n8n setup & design notes
└── logs/                          # run logs (git-ignored)
```

---

## 9. Error handling & monitoring

- **Validation** — required columns checked on load; empty/duplicate rows dropped.
- **Graceful degradation** — OpenAI failures fall back to the rule-based engine.
- **Structured exit codes** — `0` ok, `1` input error, `2` unexpected failure;
  n8n branches on the JSON `status` field.
- **Logging** — every run appends to `logs/run.log` with timestamps and levels.

---

## 10. Limitations

- The rule-based classifier is keyword-driven: it won't catch sarcasm or novel
  phrasings the lexicon doesn't cover. The OpenAI option mitigates this.
- "Emerging issues" uses a simple recent-vs-earlier window, not a statistical
  trend test — it's a directional signal, not a forecast.
- Issue categories are fixed; a new product line may need taxonomy updates.
- The sample dataset is small (20 rows) and synthetic, for demonstration.

---

## 11. Future improvements

- Swap the lexicon for a fine-tuned or few-shot LLM classifier with confidence scores.
- Persist results to a database (MySQL/Postgres) and expose SQL views for BI.
- Add a live Power BI / Looker Studio dashboard on top of the output CSV.
- Add unit tests and a CI workflow (GitHub Actions).
- Multi-language support and automatic taxonomy discovery via clustering.

---

## License

MIT — sample data is synthetic and for demonstration only.
