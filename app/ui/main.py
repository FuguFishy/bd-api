from fastapi import FastAPI
from fastapi.responses import HTMLResponse

app = FastAPI()


@app.get("/", response_class=HTMLResponse)
def ui_home():
    return """
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width,initial-scale=1" />
  <title>BD Ops Dashboard</title>
  <style>
    body {
      font-family: Arial, sans-serif;
      margin: 0;
      padding: 24px;
      background: #f7f7f7;
      color: #1a1a1a;
    }
    h1, h2 {
      margin-top: 0;
    }
    .grid {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
      gap: 16px;
      margin-bottom: 24px;
    }
    .card {
      background: white;
      border-radius: 10px;
      padding: 16px;
      box-shadow: 0 1px 4px rgba(0,0,0,0.08);
    }
    .section {
      background: white;
      border-radius: 10px;
      padding: 16px;
      margin-bottom: 24px;
      box-shadow: 0 1px 4px rgba(0,0,0,0.08);
    }
    table {
      width: 100%;
      border-collapse: collapse;
      margin-top: 12px;
      font-size: 14px;
    }
    th, td {
      text-align: left;
      padding: 10px 8px;
      border-bottom: 1px solid #e6e6e6;
      vertical-align: top;
    }
    th {
      background: #fafafa;
    }
    .status-success {
      color: #1f7a1f;
      font-weight: bold;
    }
    .status-failed {
      color: #b42318;
      font-weight: bold;
    }
    .status-running {
      color: #9a6700;
      font-weight: bold;
    }
    .muted {
      color: #666;
      font-size: 14px;
    }
    .error {
      color: #b42318;
      font-weight: bold;
    }
  </style>
</head>
<body>
  <h1>BD Ops Dashboard</h1>
  <p class="muted">SmartJobs runs, review queue, and workflow issues.</p>

  <div class="grid" id="summary"></div>

  <div class="section">
    <h2>Recent SmartJobs Runs</h2>
    <div id="scrape-runs">Loading...</div>
  </div>

  <div class="section">
    <h2>Open Review Queue</h2>
    <div id="review-queue">Loading...</div>
  </div>

  <div class="section">
    <h2>Failed Workflow Runs</h2>
    <div id="workflow-runs">Loading...</div>
  </div>

  <div class="section">
    <h2>Recent Review Actions</h2>
    <div id="review-actions">Loading...</div>
  </div>

  <script>
    function esc(value) {
      if (value === null || value === undefined) return "";
      return String(value)
        .replaceAll("&", "&amp;")
        .replaceAll("<", "&lt;")
        .replaceAll(">", "&gt;")
        .replaceAll('"', "&quot;")
        .replaceAll("'", "&#39;");
    }

    function statusClass(status) {
      const s = (status || "").toLowerCase();
      if (s === "success" || s === "resolved") return "status-success";
      if (s === "failed") return "status-failed";
      if (s === "running" || s === "new" || s === "open" || s === "pending" || s === "watchlist") return "status-running";
      return "";
    }

    function formatDate(value) {
      if (!value) return "";
      const d = new Date(value);
      if (isNaN(d)) return esc(value);
      return d.toLocaleString();
    }

    function renderTable(columns, rows) {
      if (!rows || rows.length === 0) {
        return "<p class='muted'>No data found.</p>";
      }

      const thead = "<tr>" + columns.map(col => `<th>${esc(col.label)}</th>`).join("") + "</tr>";
      const tbody = rows.map(row => {
        return "<tr>" + columns.map(col => {
          const raw = row[col.key];
          const html = col.render ? col.render(raw, row) : esc(raw);
          return `<td>${html}</td>`;
        }).join("") + "</tr>";
      }).join("");

      return `<table><thead>${thead}</thead><tbody>${tbody}</tbody></table>`;
    }

    async function loadDashboard() {
      const res = await fetch("/ops/dashboard");
      if (!res.ok) {
        throw new Error("Failed to load dashboard");
      }

      const data = await res.json();

      document.getElementById("summary").innerHTML = `
        <div class="card"><h2>${esc(data.summary.open_review_queue_count)}</h2><div class="muted">Open review items</div></div>
        <div class="card"><h2>${esc(data.summary.resolved_review_queue_count)}</h2><div class="muted">Resolved review items</div></div>
        <div class="card"><h2>${esc(data.summary.failed_workflow_count_7d)}</h2><div class="muted">Failed workflows (7d)</div></div>
        <div class="card"><h2>${esc(data.summary.failed_scrape_count_7d)}</h2><div class="muted">Failed scrapes (7d)</div></div>
      `;

      document.getElementById("scrape-runs").innerHTML = renderTable(
        [
          { key: "id", label: "ID" },
          { key: "source_name", label: "Source" },
          { key: "started_at", label: "Started", render: v => esc(formatDate(v)) },
          { key: "finished_at", label: "Finished", render: v => esc(formatDate(v)) },
          { key: "status", label: "Status", render: v => `<span class="${statusClass(v)}">${esc(v)}</span>` },
          { key: "jobs_seen", label: "Seen" },
          { key: "jobs_matched", label: "Matched" },
          { key: "review_items_created", label: "Review Items" },
          { key: "duplicates_skipped", label: "Duplicates" },
          { key: "error_count", label: "Errors" },
          { key: "error_message", label: "Error Message", render: v => v ? `<span class="error">${esc(v)}</span>` : "" }
        ],
        data.latest_scrape_runs
      );

      document.getElementById("review-queue").innerHTML = renderTable(
        [
          { key: "id", label: "ID" },
          { key: "review_status", label: "Status", render: v => `<span class="${statusClass(v)}">${esc(v)}</span>` },
          { key: "source_type", label: "Source Type" },
          { key: "review_type", label: "Review Type" },
          { key: "scraped_organisation", label: "Organisation" },
          { key: "scraped_contact_name", label: "Contact" },
          { key: "job_title", label: "Job Title" },
          { key: "best_score", label: "Best Score" },
          { key: "created_at", label: "Created", render: v => esc(formatDate(v)) }
        ],
        data.open_review_items
      );

      document.getElementById("workflow-runs").innerHTML = renderTable(
        [
          { key: "id", label: "ID" },
          { key: "workflowname", label: "Workflow" },
          { key: "runtype", label: "Run Type" },
          { key: "startedat", label: "Started", render: v => esc(formatDate(v)) },
          { key: "finishedat", label: "Finished", render: v => esc(formatDate(v)) },
          { key: "status", label: "Status", render: v => `<span class="${statusClass(v)}">${esc(v)}</span>` },
          { key: "recordsprocessed", label: "Processed" },
          { key: "recordsflagged", label: "Flagged" },
          { key: "errorsummary", label: "Error Summary", render: v => v ? `<span class="error">${esc(v)}</span>` : "" }
        ],
        data.failed_workflow_runs
      );

      document.getElementById("review-actions").innerHTML = renderTable(
        [
          { key: "id", label: "ID" },
          { key: "review_queue_id", label: "Review Queue ID" },
          { key: "action_type", label: "Action Type" },
          { key: "action_notes", label: "Notes" },
          { key: "action_by", label: "By" },
          { key: "created_at", label: "Created", render: v => esc(formatDate(v)) }
        ],
        data.recent_review_actions
      );
    }

    loadDashboard().catch(err => {
      document.getElementById("summary").innerHTML = `<div class="card error">Failed to load dashboard: ${esc(err.message)}</div>`;
      document.getElementById("scrape-runs").innerHTML = "<p class='error'>Could not load scrape runs.</p>";
      document.getElementById("review-queue").innerHTML = "<p class='error'>Could not load review queue.</p>";
      document.getElementById("workflow-runs").innerHTML = "<p class='error'>Could not load workflow runs.</p>";
      document.getElementById("review-actions").innerHTML = "<p class='error'>Could not load review actions.</p>";
    });
  </script>
</body>
</html>
    """