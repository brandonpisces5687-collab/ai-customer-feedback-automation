# Screenshots — capture guide

Drop the images named below into this folder. The main README's **Screenshots**
section already references these exact filenames, so once the files exist the
images render automatically — no further edits needed.

| Filename | What to capture | Why it matters |
|----------|-----------------|----------------|
| `n8n_workflow.png` | The n8n canvas after importing `n8n/feedback_automation_workflow.json` (all 7 nodes visible). | Visual proof of "n8n workflow automation" — the headline keyword for the role. |
| `summary_report.png` | The rendered `data/output/summary_report.md` (preview it in VS Code or paste into any Markdown viewer). | Shows the business output: sentiment, top complaints, recommended actions. |
| `powerbi_dashboard.png` | A Power BI report built on `data/output/classified_reviews.csv` — e.g. a sentiment donut, complaints-by-category bar, and urgency breakdown. | Bridges your existing Power BI strength to the AI pipeline; most recruiter-friendly image. |

## Tips

- **n8n:** `npx n8n` → open `http://localhost:5678` → Workflows → Import from File →
  select the JSON → screenshot the canvas. Zoom so all nodes and connections show.
- **Power BI:** Get Data → Text/CSV → `data/output/classified_reviews.csv`. Three
  visuals are plenty:
  1. Donut: count of `sentiment`
  2. Bar: count of `review_id` by `issue_category`, filtered to negative
  3. Stacked bar: `urgency` by `issue_category`
- Keep images under ~1 MB (PNG, ~1600px wide) so the repo stays lightweight.

Recommended size: roughly 1600×900. Crop out OS chrome / personal data.
