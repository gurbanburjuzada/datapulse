"""
main.py — DataPulse FastAPI backend.

Endpoints:
  POST /analyze   — accepts a CSV/Excel file upload, runs the LangGraph
                    agent, streams progress via Server-Sent Events (SSE),
                    and emits the final report as a JSON event.

  GET  /health    — simple health check for deployment monitoring.

SSE protocol used here:
  Each event is "data: <json_string>\n\n"
  The frontend EventSource listens for these and updates the UI.

  Event shapes:
    {"type": "progress", "message": "..."}
    {"type": "report",   "data": { ...ReportOutput... }}
    {"type": "error",    "message": "..."}
"""

import json
import os
import tempfile
import asyncio
from pathlib import Path
from dotenv import load_dotenv

from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse

from agent.graph import compiled_graph
from agent.state import AnalysisState

app = FastAPI(title="DataPulse API", version="1.0.0")
load_dotenv()

# ── CORS — allow the React dev server and the deployed frontend ───────────────
ALLOWED_ORIGINS = os.environ.get(
    "ALLOWED_ORIGINS",
    "http://localhost:5173,http://localhost:3000"
).split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"]
)

ALLOWED_EXTENSIONS = [".csv", ".xls", ".xlsx"]
MAX_FILE_SIZE_MB = 50

# ─────────────────────────────────────────────────────────────────────────────
# Health check
# ─────────────────────────────────────────────────────────────────────────────


@app.get('/health')
def health():
    return {"status": "ok", "service": "datapulse-api"}

# ─────────────────────────────────────────────────────────────────────────────
# Main analysis endpoint
# ─────────────────────────────────────────────────────────────────────────────


@app.post('/analyze')
async def analyze(file: UploadFile = File(...)):
    """
    Accept a CSV or Excel file, stream SSE progress events, emit final report.
    """
    # ── Validate file ─────────────────────────────────────────────────────
    suffix = Path(file.filename).suffix.lower()
    if suffix not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type '{suffix}'. Upload a CSV or Excel file.",
        )

    contents = await file.read()
    size_mb = len(contents) / (1024 * 1024)
    if size_mb > MAX_FILE_SIZE_MB:
        raise HTTPException(
            status_code=413,
            detail=f"File too large ({size_mb:.1f} MB). Limit is {MAX_FILE_SIZE_MB} MB.",
        )

    return StreamingResponse(
        _stream_analysis(contents, file.filename),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no"   # prevents Nginx from buffering SSE
        }
    )


async def _stream_analysis(contents: bytes, filename: str):
    """
    Generator that:
      1. Saves the file to a temp path
      2. Runs the LangGraph agent synchronously in a thread
         (pandas is not async-native; asyncio.to_thread keeps the event loop free)
      3. Streams SSE events as the agent progresses
    """
    def _sse(payload: dict) -> str:
        return f"data: {json.dumps(payload)}\n\n"

    # Save uploaded bytes to a temp file
    with tempfile.NamedTemporaryFile(delete=False, suffix=Path(filename).suffix) as tmp:
        tmp.write(contents)
        tmp_path = tmp.name

    try:
        # Initial state
        initial_state: AnalysisState = {
            "file_path": tmp_path,
            "file_name": filename,
            "schema_result": None,
            "outlier_result": None,
            "distribution_result": None,
            "duplicate_result": None,
            "correlation_result": None,
            "quality_score": None,
            "llm_summary": None,
            "progress": [],
            "report": None,
            "error": None,
            "_df_json": None
        }

        # Run the graph in a thread so the event loop stays responsive
        # We collect state snapshots via astream
        seen_progress: list[str] = []

        async for chunk in compiled_graph.astream(initial_state):
            # chunk is {node_name: partial_state_dict}
            for node_name, partial in chunk.items():
                new_messages = partial.get("progress", [])
                for msg in new_messages:
                    if msg not in seen_progress:
                        seen_progress.append(msg)
                        yield _sse({"type": "progress", "message": msg})
                        await asyncio.sleep(0)   # yield control back to event loop

                # If report is ready, emit it
                if partial.get("report"):
                    yield _sse({"type": "report", "data": partial["report"]})
                    await asyncio.sleep(0)

                if partial.get("error"):
                    yield _sse({"type": "error", "message": partial["error"]})
                    return

    except Exception as exc:
        yield _sse({"type": "error", "message": f"Unexpected server error: {str(exc)}"})

    finally:
        # Always clean-up the temp file
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
