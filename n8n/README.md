# n8n Workflow — Setup & Design

This folder contains the n8n automation that orchestrates the Python pipeline.

## Workflow design

```
 ┌──────────────────┐
 │  Manual Trigger  │──┐
 └──────────────────┘  │
 ┌──────────────────┐  │   ┌─────────────────────┐   ┌───────────────────────┐
 │  Daily Schedule  │──┴──▶│ Run Python Pipeline │──▶│ Parse Pipeline Output │
 └──────────────────┘      │  (Execute Command)  │   │      (Code node)      │
                           └─────────────────────┘   └───────────┬───────────┘
                                                                 │
                                                     ┌───────────▼────────────┐
                                                     │   Pipeline Succeeded?   │
                                                     │        (IF node)        │
                                                     └─────┬──────────────┬────┘
                                                       true│              │false
                                              ┌────────────▼───┐    ┌─────▼──────────┐
                                              │ Notify Success │    │ Notify Failure │
                                              └────────────────┘    └────────────────┘
```

### Node-by-node

| Node | Type | Purpose |
|------|------|---------|
| Manual Trigger | Manual Trigger | Run on demand while testing / demoing. |
| Daily Schedule | Schedule Trigger | Run automatically every 24h in production. |
| Run Python Pipeline | Execute Command | Calls `process_feedback.py`; the script prints a JSON status line on stdout. |
| Parse Pipeline Output | Code | Parses the last stdout line into structured JSON so later nodes can branch. |
| Pipeline Succeeded? | IF | Routes on `status == "ok"`. |
| Notify Success / Failure | No-Op (placeholder) | Swap for Email / Slack / Google Sheets nodes. |

The two notification nodes are **No-Op placeholders** so the workflow imports
and runs without any credentials. Replace them with real nodes once you wire up
email/Slack (see below).

## Import the workflow

1. Install n8n (free, self-hosted):
   ```bash
   npx n8n
   ```
   Then open `http://localhost:5678`.
2. In the n8n UI: **Workflows → Import from File →** select
   `feedback_automation_workflow.json`.
3. Open the **Run Python Pipeline** node and edit the absolute paths to match
   your machine (they currently point at this project's location).
4. Click **Test workflow** (uses the Manual Trigger).

## Optional: write results to Google Sheets (free)

To satisfy the "export to Google Sheets" requirement without paid tooling:

1. Add a **Google Sheets** node after *Pipeline Succeeded? → true*.
2. Authenticate with a free Google account (OAuth2).
3. Operation: **Append or Update**. Map the summary fields from
   `{{ $json.summary }}` to your sheet columns.

If you prefer to stay fully offline, the pipeline already writes a
dashboard-ready CSV (`data/output/classified_reviews.csv`) that Google Sheets,
Excel, or Power BI can import directly.

## Optional: turn on the OpenAI classifier

The Execute Command node inherits the n8n process environment. Set
`OPENAI_API_KEY` before launching n8n, and remove `--no-openai` if you added it.
With no key set, the pipeline automatically uses the offline rule-based engine.
