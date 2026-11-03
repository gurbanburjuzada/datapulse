"""
graph.py — DataPulse LangGraph backend.

Key changes vs previous version:
- DataFrame is cached in a module-level dict (keyed by job id) instead of
  being serialised to JSON in state. This removes 5x to_json/read_json
  round-trips which were the dominant performance cost.
- generate_summary uses asyncio.to_thread so the blocking OpenAI HTTP
  call no longer stalls the event loop.
- All tool nodes remain separate for real-time SSE progress streaming.
"""

from __future__ import annotations

import asyncio
import os
import uuid
from typing import Any

import pandas as pd
import logging
import time
from dotenv import load_dotenv
from langgraph.graph import StateGraph, END
from langgraph.graph.state import CompiledStateGraph
from openai import OpenAI

from agent.state import (
    AnalysisState,
    ReportOutput,
    compute_quality_score,
)
from agent.tools.schema_inspector import run_schema_inspector
from agent.tools.outlier_detector import run_outlier_detector
from agent.tools.distribution_profiler import run_distribution_profiler
from agent.tools.duplicate_checker import run_duplicate_checker
from agent.tools.correlation_mapper import run_correlation_mapper

load_dotenv()

_openai = OpenAI()
_MODEL = "gpt-4o-mini"


logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("datapulse.graph")
# Module-level DataFrame cache — avoids JSON serialisation between nodes.
# Keys are UUIDs generated per analysis run; cleaned up in build_report.
_DF_CACHE: dict[str, pd.DataFrame] = {}


def _get_df(state: AnalysisState) -> pd.DataFrame:
    """Retrieve the cached DataFrame for this run."""
    return _DF_CACHE[state["_df_json"]]  # _df_json stores the cache key


# ─────────────────────────────────────────────────────────────────────────────
# Node 1: load_file
# ─────────────────────────────────────────────────────────────────────────────

def load_file(state: AnalysisState) -> dict[str, Any]:
    log.debug("→ load_file START")
    t = time.perf_counter()

    path = state["file_path"]
    file_name = state["file_name"]
    progress = list(state.get("progress", []))

    try:
        progress.append(f"📂 Reading '{file_name}'…")
        log.debug("  load_file: calling pd.read_csv/excel")

        if file_name.endswith(".csv"):
            df = pd.read_csv(path)
        elif file_name.endswith((".xlsx", ".xls")):
            df = pd.read_excel(path)
        else:
            raise ValueError(f"Unsupported file type: {file_name}")

        log.debug("  load_file: file read OK — %d rows × %d cols", len(df), len(df.columns))

        cache_key = str(uuid.uuid4())
        _DF_CACHE[cache_key] = df

        progress.append(f"✅ Loaded {len(df):,} rows × {len(df.columns)} columns.")
        log.debug("← load_file END (%.3fs)", time.perf_counter() - t)
        return {"progress": progress, "_df_json": cache_key, "error": None}

    except Exception as exc:
        log.exception("  load_file EXCEPTION: %s", exc)
        progress.append(f"❌ Failed to read file: {exc}")
        return {"progress": progress, "error": str(exc)}


# ─────────────────────────────────────────────────────────────────────────────
# Nodes 2–6: one node per tool
# ─────────────────────────────────────────────────────────────────────────────

async def node_schema(state: AnalysisState) -> dict[str, Any]:
    log.debug("→ node_schema START")
    t = time.perf_counter()
    progress = list(state.get("progress", []))
    if state.get("error"):
        return {"progress": progress}

    progress.append("🔍 Inspecting schema and column types…")
    df = _get_df(state)
    log.debug("  node_schema: calling run_schema_inspector")
    result = await asyncio.to_thread(run_schema_inspector, df)
    log.debug("← node_schema END (%.3fs)", time.perf_counter() - t)
    return {"progress": progress, "schema_result": result}


async def node_distribution(state: AnalysisState) -> dict[str, Any]:
    log.debug("→ node_distribution START")
    t = time.perf_counter()
    progress = list(state.get("progress", []))
    if state.get("error"):
        return {"progress": progress}

    progress.append("📊 Profiling distributions…")
    df = _get_df(state)
    log.debug("  node_distribution: calling run_distribution_profiler")
    result = await asyncio.to_thread(run_distribution_profiler, df)
    log.debug("← node_distribution END (%.3fs)", time.perf_counter() - t)
    return {"progress": progress, "distribution_result": result}


async def node_outliers(state: AnalysisState) -> dict[str, Any]:
    log.debug("→ node_outliers START")
    t = time.perf_counter()
    progress = list(state.get("progress", []))
    if state.get("error"):
        return {"progress": progress}

    progress.append("🎯 Detecting outliers…")
    df = _get_df(state)
    log.debug("  node_outliers: calling run_outlier_detector")
    result = await asyncio.to_thread(run_outlier_detector, df)
    log.debug("← node_outliers END (%.3fs)", time.perf_counter() - t)
    return {"progress": progress, "outlier_result": result}


async def node_duplicates(state: AnalysisState) -> dict[str, Any]:
    log.debug("→ node_duplicates START")
    t = time.perf_counter()
    progress = list(state.get("progress", []))
    if state.get("error"):
        return {"progress": progress}

    progress.append("🔁 Checking for duplicate rows…")
    df = _get_df(state)
    log.debug("  node_duplicates: calling run_duplicate_checker")
    result = await asyncio.to_thread(run_duplicate_checker, df)
    log.debug("← node_duplicates END (%.3fs)", time.perf_counter() - t)
    return {"progress": progress, "duplicate_result": result}


async def node_correlation(state: AnalysisState) -> dict[str, Any]:
    log.debug("→ node_correlation START")
    t = time.perf_counter()
    progress = list(state.get("progress", []))
    if state.get("error"):
        return {"progress": progress}

    progress.append("🔗 Computing correlations…")
    df = _get_df(state)
    log.debug("  node_correlation: calling run_correlation_mapper")
    result = await asyncio.to_thread(run_correlation_mapper, df)
    progress.append("✅ All analysis tools completed.")
    log.debug("← node_correlation END (%.3fs)", time.perf_counter() - t)
    return {"progress": progress, "correlation_result": result}


# ─────────────────────────────────────────────────────────────────────────────
# Node 7: score_results
# ─────────────────────────────────────────────────────────────────────────────

def score_results(state: AnalysisState) -> dict[str, Any]:
    log.debug("→ score_results START")
    t = time.perf_counter()
    progress = list(state.get("progress", []))
    if state.get("error"):
        return {"progress": progress}

    progress.append("🧮 Computing quality score…")
    quality_score = compute_quality_score(
        schema=state["schema_result"],
        outliers=state["outlier_result"],
        duplicates=state["duplicate_result"],
    )
    grade_emoji = {"A": "🟢", "B": "🟡", "C": "🟠", "D": "🔴", "F": "🔴"}
    emoji = grade_emoji.get(quality_score.grade, "⚪")
    progress.append(
        f"{emoji} Quality score: {quality_score.score}/100 "
        f"(Grade {quality_score.grade}) — "
        f"{quality_score.critical_count} critical, "
        f"{quality_score.warning_count} warnings, "
        f"{quality_score.info_count} info."
    )
    log.debug("← score_results END (%.3fs)", time.perf_counter() - t)
    return {"progress": progress, "quality_score": quality_score}


# ─────────────────────────────────────────────────────────────────────────────
# Node 8: generate_summary  — OpenAI call moved to a thread
# ─────────────────────────────────────────────────────────────────────────────

async def generate_summary(state: AnalysisState) -> dict[str, Any]:
    log.debug("→ generate_summary START")
    t = time.perf_counter()
    progress = list(state.get("progress", []))
    if state.get("error"):
        return {"progress": progress}

    progress.append("✍️ Generating natural-language summary…")

    schema = state["schema_result"]
    outlier = state["outlier_result"]
    dist = state["distribution_result"]
    dups = state["duplicate_result"]
    corr = state["correlation_result"]
    score = state["quality_score"]

    all_findings = (
        schema.findings + outlier.findings + dist.findings
        + dups.findings + corr.findings
    )
    severity_order = {"critical": 0, "warning": 1, "info": 2}
    all_findings.sort(key=lambda f: severity_order[f.severity])

    findings_text = "\n".join(
        f"[{f.severity.upper()}] {f.title}: {f.detail} → {f.recommendation}"
        for f in all_findings[:20]
    )

    prompt = f"""You are a senior data scientist reviewing an automated data quality report.

Dataset: {state['file_name']}
Shape: {schema.row_count:,} rows × {schema.col_count} columns
Quality score: {score.score}/100 (Grade {score.grade})
Critical issues: {score.critical_count} | Warnings: {score.warning_count}

Top findings:
{findings_text}

Write a concise 4–6 sentence plain-English summary. Open with the overall \
quality, highlight the most critical issues, end with what looks healthy. \
No bullet points."""

    def _call_openai() -> str:
        log.debug("  generate_summary: OpenAI request firing")
        r = _openai.chat.completions.create(
            model=_MODEL,
            messages=[
                {"role": "system", "content": "You are a senior data scientist. Be direct and concise."},
                {"role": "user",   "content": prompt},
            ],
            max_tokens=400,
            temperature=0.3,
        )
        log.debug("  generate_summary: OpenAI response received")
        return r.choices[0].message.content.strip()

    try:
        llm_summary = await asyncio.to_thread(_call_openai)
    except Exception as exc:
        log.exception("  generate_summary EXCEPTION: %s", exc)
        llm_summary = (
            f"Summary generation failed: {exc}. "
            "Please review the findings list directly."
        )

    progress.append("✅ Summary ready.")
    log.debug("← generate_summary END (%.3fs)", time.perf_counter() - t)
    return {"progress": progress, "llm_summary": llm_summary}


# ─────────────────────────────────────────────────────────────────────────────
# Node 9: build_report
# ─────────────────────────────────────────────────────────────────────────────

def build_report(state: AnalysisState) -> dict[str, Any]:
    log.debug("→ build_report START")
    t = time.perf_counter()
    progress = list(state.get("progress", []))
    if state.get("error"):
        _DF_CACHE.pop(state.get("_df_json", ""), None)
        return {"progress": progress}

    progress.append("📋 Building final report…")

    try:
        schema = state["schema_result"]
        outlier = state["outlier_result"]
        dist = state["distribution_result"]
        dups = state["duplicate_result"]
        corr = state["correlation_result"]
        score = state["quality_score"]

        all_findings = (
            schema.findings + outlier.findings + dist.findings
            + dups.findings + corr.findings
        )
        severity_order = {"critical": 0, "warning": 1, "info": 2}
        all_findings.sort(key=lambda f: severity_order[f.severity])

        log.debug("  build_report: constructing ReportOutput")
        log.debug("  build_report: %d findings, %d columns, %d distributions, %d outlier_cols",
                  len(all_findings), len(schema.columns),
                  len(dist.distributions), len(outlier.outlier_columns))
        log.debug("  build_report: heatmap_data type=%s len=%s",
                  type(corr.heatmap_data), len(corr.heatmap_data) if corr.heatmap_data else 0)
        log.debug("  build_report: llm_summary type=%s", type(state["llm_summary"]))

        report = ReportOutput(
            file_name=state["file_name"],
            row_count=schema.row_count,
            col_count=schema.col_count,
            quality_score=score,
            columns=schema.columns,
            findings=all_findings,
            distributions=dist.distributions,
            outlier_columns=outlier.outlier_columns,
            duplicate_info={
                "exact_duplicate_rows":  dups.exact_duplicate_rows,
                "exact_duplicate_pct":   dups.exact_duplicate_pct,
                "near_duplicate_groups": dups.near_duplicate_groups,
            },
            heatmap_data=corr.heatmap_data,
            llm_summary=state["llm_summary"],
        )

        log.debug("  build_report: ReportOutput constructed OK")
        log.debug("  build_report: calling model_dump()")

        report_dict = report.model_dump()

        log.debug("  build_report: model_dump() OK, keys=%s", list(report_dict.keys()))

        _DF_CACHE.pop(state["_df_json"], None)
        progress.append("🎉 Analysis complete!")
        log.debug("← build_report END (%.3fs)", time.perf_counter() - t)
        return {"progress": progress, "report": report_dict}

    except Exception as exc:
        log.exception("  build_report EXCEPTION: %s", exc)
        _DF_CACHE.pop(state.get("_df_json", ""), None)
        return {"progress": progress, "error": f"Failed to build report: {exc}"}

# ─────────────────────────────────────────────────────────────────────────────
# Routing + graph assembly
# ─────────────────────────────────────────────────────────────────────────────


def should_continue(state: AnalysisState) -> str:
    return END if state.get("error") else "node_schema"


def build_graph() -> CompiledStateGraph:
    graph = StateGraph(AnalysisState)

    graph.add_node("load_file",         load_file)
    graph.add_node("node_schema",       node_schema)
    graph.add_node("node_distribution", node_distribution)
    graph.add_node("node_outliers",     node_outliers)
    graph.add_node("node_duplicates",   node_duplicates)
    graph.add_node("node_correlation",  node_correlation)
    graph.add_node("score_results",     score_results)
    graph.add_node("generate_summary",  generate_summary)
    graph.add_node("build_report",      build_report)

    graph.set_entry_point("load_file")
    graph.add_conditional_edges("load_file", should_continue)

    graph.add_edge("node_schema",       "node_distribution")
    graph.add_edge("node_distribution", "node_outliers")
    graph.add_edge("node_outliers",     "node_duplicates")
    graph.add_edge("node_duplicates",   "node_correlation")
    graph.add_edge("node_correlation",  "score_results")
    graph.add_edge("score_results",     "generate_summary")
    graph.add_edge("generate_summary",  "build_report")
    graph.add_edge("build_report",      END)

    return graph.compile()


compiled_graph: CompiledStateGraph = build_graph()
