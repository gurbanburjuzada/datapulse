"""
state.py — Single source of truth for all data shapes in DataPulse.

Every tool returns one of the Result models below.
The LangGraph StateGraph holds AnalysisState throughout execution.
FastAPI serialises the final ReportOutput to the frontend.

Design rule: if you're unsure where a field lives, it belongs here.
"""

from __future__ import annotations

from enum import Enum
from typing import Any, Optional
from pydantic import BaseModel, Field
from typing_extensions import TypedDict

# ── Severity levels ──────────────────────────────────────────────────────────


class Severity(str, Enum):
    CRITICAL = "critical"   # blocks modelling (e.g. > 40 % nulls in target col)
    WARNING = "warning"     # degrades quality  (e.g. moderate skew)
    INFO = "info"           # good-to-know      (e.g. low cardinality cat col)

# ── One finding = one actionable observation ─────────────────────────────────


class Finding(BaseModel):
    severity: Severity
    column: Optional[str] = None   # None → dataset-level finding
    title: str
    detail: str                    # what was measured / found
    recommendation: str            # concrete fix, 1–2 sentences

# ── Per-tool result models ────────────────────────────────────────────────────


class ColumnMeta(BaseModel):
    name: str
    dtype: str
    null_count: int
    null_pct: float          # pct stands for percentage here
    unique_count: int
    cardinality_pct: float   # unique / total rows * 100
    sample_values: list[Any]


class SchemaResult(BaseModel):
    """Output of schema_inspector tool."""
    row_count: int
    col_count: int
    columns: list[ColumnMeta]
    findings: list[Finding]


class OutlierInfo(BaseModel):
    column: str
    iqr_outlier_count: int
    zscore_outlier_count: int
    iqr_outlier_pct: float
    zscore_outlier_pct: float
    lower_bound: float
    upper_bound: float


class OutlierResult(BaseModel):
    """Output of outlier_detector tool."""
    outlier_columns: list[OutlierInfo]
    findings: list[Finding]


class DistributionInfo(BaseModel):
    column:   str
    mean:     Optional[float] = None
    median:   Optional[float] = None
    std:      Optional[float] = None
    skewness: Optional[float] = None
    kurtosis: Optional[float] = None
    # For categorical columns
    top_values: Optional[list[dict[str, Any]]] = None   # [{"value": x, "count": n}]
    is_imbalanced: Optional[bool] = None                # for potential target cols


class DistributionResult(BaseModel):
    """Output of distribution_profiler tool."""
    distributions: list[DistributionInfo]
    findings: list[Finding]


class DuplicateResult(BaseModel):
    """Output of duplicate_checker tool."""
    exact_duplicate_rows: int
    exact_duplicate_pct: float
    near_duplicate_groups: int    # groups of rows that differ only in 1 column
    findings: list[Finding]


class CorrelationPair(BaseModel):
    col_a: str
    col_b: str
    pearson_r: float
    abs_r: float


class CorrelationResult(BaseModel):
    """Output of a correlation_mapper tool"""
    pairs: list[CorrelationPair]   # all numeric pairs, sorted by abs_r desc
    high_corr_pairs: list[CorrelationPair]   # abs_r > 0.85
    heatmap_data: dict[str, Any]   # {columns: [...], matrix: [[...]]}
    findings: list[Finding]

# ── Quality score ─────────────────────────────────────────────────────────────


class QualityScore(BaseModel):
    score: int   # 0–100
    grade: str   # A / B / C / D / F
    critical_count: int
    warning_count: int
    info_count: int


def compute_grade(score: int):
    if score >= 90: return "A"
    if score >= 75: return "B"
    if score >= 60: return "C"
    if score >= 45: return "D"
    return "F"


def compute_quality_score(
        schema:          SchemaResult,
        outliers:        OutlierResult,
        duplicates:      DuplicateResult
) -> QualityScore:
    """
    Heuristic scoring — deduct points for problems, floor at 0.

    Deductions:
      - Each critical finding : -15 pts
      - Each warning finding  :  -5 pts
      - Each info finding     :  -1 pt
      - Exact duplicate rows  :  up to -10 pts (proportional to pct)
    """
    all_findings = (
        schema.findings
        + outliers.findings
        + duplicates.findings
    )
    critical = sum(1 for f in all_findings if f.severity == Severity.CRITICAL)
    warning = sum(1 for f in all_findings if f.severity == Severity.WARNING)
    info = sum(1 for f in all_findings if f.severity == Severity.INFO)

    score = 100
    score -= (15 * critical + 5 * warning + info)
    score -= min(10, int(duplicates.exact_duplicate_pct * 2))
    score = max(0, score)

    return QualityScore(
        score=score,
        grade=compute_grade(score),
        critical_count=critical,
        warning_count=warning,
        info_count=info
    )

# ── LangGraph agent state ─────────────────────────────────────────────────────


class AnalysisState(TypedDict):
    """
    Flows through every node in the StateGraph.
    Fields are populated progressively as nodes run.
    """
    # Input
    file_path: str
    file_name: str
    _df_json: Optional[str]
    # Tool outputs (None until node runs)
    schema_result:       Optional[SchemaResult]
    outlier_result:      Optional[OutlierResult]
    distribution_result: Optional[DistributionResult]
    duplicate_result:    Optional[DuplicateResult]
    correlation_result:  Optional[CorrelationResult]
    # Computed
    quality_score: Optional[QualityScore]
    # llm-generated
    llm_summary: Optional[str]
    # Progress messages streamed to frontend
    progress: list[str]
    # Final serialisable report (populated at the end)
    report: Optional[dict[str, Any]]
    # Error Handling
    error: Optional[str]

# ── Final API response ────────────────────────────────────────────────────────


class ReportOutput(BaseModel):
    """
    Serialised by FastAPI and sent to the React frontend.
    All chart data is pre-computed here; frontend just renders it.
    """
    file_name:         str
    row_count:         int
    col_count:         int
    quality_score:     QualityScore
    columns:           list[ColumnMeta]
    findings:          list[Finding]   # all findings, severity-sorted
    distributions:     Optional[list[DistributionInfo]]
    outlier_columns:   Optional[list[OutlierInfo]]
    duplicate_info:    dict[str, Any]
    heatmap_data:      dict[str, Any]
    llm_summary:       str
