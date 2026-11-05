# DataPulse — Automated Data Quality Agent

DataPulse is an agentic data quality analysis system. Upload any CSV or Excel file and a LangGraph agent autonomously runs five statistical analysis tools, scores your dataset's quality, and produces a plain-English report written by GPT-4o mini — all streamed live to the browser.

Built as a portfolio project to demonstrate end-to-end ML engineering: agentic orchestration, statistical profiling, async streaming APIs, and cloud deployment on AWS EC2.

---

## What It Does

Drop a dataset → the agent runs in real time → you get:

- **Quality score (0–100)** with a letter grade and breakdown by severity
- **Schema inspection** — column types, null rates, cardinality, unique value samples
- **Outlier detection** — IQR and Z-score methods per numeric column
- **Distribution profiling** — skewness, kurtosis, class imbalance detection
- **Duplicate detection** — exact and near-duplicate row groups
- **Correlation mapping** — Pearson matrix with multicollinearity warnings
- **AI summary** — GPT-4o mini synthesises all findings into a 4–6 sentence plain-English report

Every finding includes a severity level (critical / warning / info) and a concrete recommendation for how to fix the issue before modelling.

---

## Architecture

```
React frontend (Vite + Tailwind)
        │  file upload → POST /analyze
        │  ← SSE stream (progress + report)
        ▼
FastAPI backend
        │
        ▼
LangGraph StateGraph
   load_file → run_tools → score_results → generate_summary → build_report
                   │
        ┌──────────┼──────────┐
        ▼          ▼          ▼
  schema_      outlier_   distribution_
  inspector    detector    profiler
        ▼          ▼
  duplicate_  correlation_
  checker      mapper
        │
        ▼
   OpenAI GPT-4o mini  (natural language summary)
```

The agent uses **Server-Sent Events (SSE)** to stream progress messages to the frontend as each node runs — the browser shows a live log rather than a loading spinner.

---

## Tech Stack

| Layer | Technology | Purpose |
|---|---|---|
| Frontend | React 19 + Vite + Tailwind CSS | File upload UI, live progress stream, tabbed report |
| Backend | FastAPI + Uvicorn | Async REST API, SSE streaming, file validation |
| Agent | LangGraph `StateGraph` | Multi-node agent orchestration |
| Analysis | pandas, numpy, scipy | Statistical profiling tools |
| LLM | OpenAI GPT-4o mini | Natural language summary generation |
| Data models | Pydantic v2 | Type-safe tool outputs and API contracts |
| Containerisation | Docker + docker-compose | Reproducible local and production environment |
| Deployment | AWS EC2 (t2.micro) + Nginx | Cloud hosting with reverse proxy and access control |

---

## Project Structure

```
datapulse/
├── backend/
│   ├── main.py                    # FastAPI app — /analyze SSE endpoint
│   ├── requirements.txt
│   ├── Dockerfile
│   └── agent/
│       ├── state.py               # Pydantic models + AnalysisState TypedDict
│       ├── graph.py               # LangGraph StateGraph definition
│       └── tools/
│           ├── schema_inspector.py      # dtypes, nulls, cardinality
│           ├── outlier_detector.py      # IQR + Z-score outlier detection
│           ├── distribution_profiler.py # skewness, kurtosis, class balance
│           ├── duplicate_checker.py     # exact + near-duplicate detection
│           └── correlation_mapper.py    # Pearson matrix, multicollinearity
├── frontend/
│   ├── src/
│   │   ├── App.jsx                # Main app — SSE client, phase state machine
│   │   ├── index.css              # Global styles and CSS design tokens
│   │   └── components/
│   │       ├── FileDropzone.jsx   # Drag-and-drop upload
│   │       ├── ProgressStream.jsx # Live agent log panel
│   │       ├── QualityScore.jsx   # Animated ring chart + grade
│   │       ├── ReportPanel.jsx    # Tabbed report: findings, schema, heatmap, summary
│   │       └── QualityScore.jsx
│   ├── vite.config.js             # Dev proxy: /analyze → localhost:8000
│   └── Dockerfile
├── nginx/
│   └── nginx.conf                 # EC2 reverse proxy + HTTP Basic Auth
├── docker-compose.yml
└── .env.example
```

---

## Running Locally

**Prerequisites:** Python 3.11+, Node.js 20+, an OpenAI API key.

```bash
# 1. Clone and enter the project
git clone https://github.com/YOUR_USERNAME/datapulse.git
cd datapulse

# 2. Backend
cd backend
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt

# Create .env with your key
echo "OPENAI_API_KEY=sk-..." > .env

uvicorn main:app --reload --port 8000

# 3. Frontend (new terminal)
cd frontend
npm install
npm run dev                     # opens http://localhost:5173
```

No `VITE_API_URL` needed in `frontend/.env` — Vite proxies `/analyze` to port 8000 automatically during development.

---

## Deploying to AWS EC2

**One-time setup (AWS console):**
1. Launch a `t2.micro` instance — Ubuntu 22.04 LTS (free tier eligible)
2. Security Group: allow SSH (port 22) from your IP, HTTP (port 80) from anywhere
3. Download the `.pem` key → `chmod 400 your-key.pem`
4. SSH in: `ssh -i your-key.pem ubuntu@<ec2-public-ip>`

**On the instance:**
```bash
# Install Docker
sudo apt-get update && sudo apt-get install -y docker.io docker-compose-plugin
sudo usermod -aG docker ubuntu   # then log out and back in

# Install Nginx
sudo apt-get install -y nginx apache2-utils

# Copy project (from your local machine)
scp -i your-key.pem -r ./datapulse ubuntu@<ec2-ip>:~/datapulse

# Set API key
echo "OPENAI_API_KEY=sk-..." > ~/datapulse/.env

# Build and start containers
cd ~/datapulse
docker compose build
docker compose up -d

# Configure Nginx with password protection
sudo htpasswd -c /etc/nginx/.htpasswd datapulse
sudo cp nginx/nginx.conf /etc/nginx/sites-available/datapulse
sudo ln -s /etc/nginx/sites-available/datapulse /etc/nginx/sites-enabled/datapulse
sudo rm -f /etc/nginx/sites-enabled/default
sudo nginx -t && sudo systemctl reload nginx
```

The app is now live at `http://<ec2-public-ip>` behind HTTP Basic Auth. Share the URL and password in your resume.

**Useful commands:**
```bash
docker compose logs -f           # live logs from both containers
docker compose ps                # check container status
docker compose restart backend   # restart after a code change
sudo systemctl reload nginx      # apply nginx config changes without downtime
```

---

## Key Engineering Decisions

**Why LangGraph instead of a plain function pipeline?**
LangGraph's `StateGraph` gives explicit node boundaries, a typed shared state, and conditional routing (early exit on file errors). This maps directly to how production ML pipelines are structured and makes each analysis step independently testable.

**Why SSE instead of WebSockets?**
SSE is unidirectional (server → client) and works over plain HTTP — no connection upgrade, no additional infrastructure, and Nginx proxies it correctly with `proxy_buffering off`. For this use case (streaming progress, then one final JSON payload) SSE is simpler and more robust than WebSockets.

**Why run tools in `asyncio.to_thread`?**
pandas and scipy are synchronous and CPU-bound. Running them directly in an async function would block the event loop and stall the SSE stream. `asyncio.to_thread` offloads the computation to a thread pool, keeping the event loop free to flush SSE messages as the agent progresses.

**Why GPT-4o mini for the summary?**
The structured findings (severity, column names, statistics) are already computed deterministically. The LLM's only job is to synthesise them into readable prose — a task where a small, fast, cheap model works as well as a large one. `temperature=0.3` keeps the output factual and consistent.

---

## Supported File Formats

| Format | Extension | Notes |
|---|---|---|
| CSV | `.csv` | Any delimiter detected automatically by pandas |
| Excel | `.xlsx` | Multi-sheet files use the first sheet |
| Excel (legacy) | `.xls` | Supported via `xlrd` |

Maximum file size: **50 MB**. For larger datasets, consider sampling before uploading.
