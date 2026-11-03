"""
duplicate_checker.py

Detects two kinds of duplicate rows:
  - Exact: all column values identical
  - Near: rows that differ in only one column

Near-duplicate detection uses hash counting only — no frozenset
storage, no index lookups, no nested loops over matching rows.
"""

import time
import logging
import pandas as pd
from agent.state import DuplicateResult, Finding, Severity

log = logging.getLogger("datapulse.duplicates")


def run_duplicate_checker(df: pd.DataFrame) -> DuplicateResult:
    log.debug("  duplicate_checker: START")
    t = time.perf_counter()
    n = len(df)
    findings: list[Finding] = []

    # ── Exact duplicates ──────────────────────────────────────────────────
    exact_dup_count = int(df.duplicated(keep="first").sum())
    exact_dup_pct   = round(exact_dup_count / n * 100, 2) if n else 0.0

    # ── Near-duplicates ───────────────────────────────────────────────────
    near_dup_groups = 0
    if n <= 50_000 and len(df.columns) > 1:
        log.debug("  near_dup: START (%d cols)", len(df.columns))
        near_dup_groups = _count_near_duplicate_groups(df)
        log.debug("  near_dup: END — %d groups", near_dup_groups)

    # ── Findings ──────────────────────────────────────────────────────────
    if exact_dup_pct > 5:
        findings.append(Finding(
            severity=Severity.CRITICAL,
            column=None,
            title="High proportion of exact duplicate rows",
            detail=(
                f"{exact_dup_count:,} rows ({exact_dup_pct:.1f}%) are exact "
                "duplicates of at least one other row."
            ),
            recommendation=(
                "Run df.drop_duplicates() before any analysis or modelling. "
                "Duplicate rows inflate apparent sample size and bias models "
                "toward the patterns they repeat."
            ),
        ))
    elif exact_dup_count > 0:
        findings.append(Finding(
            severity=Severity.WARNING,
            column=None,
            title="Exact duplicate rows detected",
            detail=f"{exact_dup_count:,} rows ({exact_dup_pct:.1f}%) are duplicates.",
            recommendation=(
                "Deduplicate with df.drop_duplicates() and investigate "
                "the source — duplicates often indicate a join error or "
                "double-ingestion in the pipeline."
            ),
        ))

    if near_dup_groups > 0:
        findings.append(Finding(
            severity=Severity.INFO,
            column=None,
            title="Near-duplicate row groups detected",
            detail=(
                f"{near_dup_groups} group(s) of rows differ in only one column — "
                "possible data-entry variants or partially-merged records."
            ),
            recommendation=(
                "Inspect these groups manually. They may be legitimate variants "
                "or errors needing deduplication."
            ),
        ))

    log.debug("  duplicate_checker: END (%.3fs)", time.perf_counter() - t)
    return DuplicateResult(
        exact_duplicate_rows=exact_dup_count,
        exact_duplicate_pct=exact_dup_pct,
        near_duplicate_groups=near_dup_groups,
        findings=findings,
    )


def _count_near_duplicate_groups(df: pd.DataFrame) -> int:
    """
    Fast O(n * cols) near-duplicate detection.

    For each column c, hash every row on all OTHER columns.
    A hash appearing more than once means those rows match on
    every column except c — they are near-duplicates.

    Uses only hash arithmetic — no frozenset, no index scans,
    no nested loops. Completes in milliseconds on 100k rows.
    """
    str_df = df.fillna("__NULL__").astype(str)
    seen: set[int] = set()
    groups_found = 0

    for col in str_df.columns:
        other_cols = [c for c in str_df.columns if c != col]
        if not other_cols:
            continue

        row_hashes = pd.util.hash_pandas_object(
            str_df[other_cols], index=False
        )
        counts = row_hashes.value_counts()
        dup_hashes = counts[counts > 1].index

        for h in dup_hashes:
            # Key is unique per (omitted_column, hash) pair
            key = hash((col, int(h)))
            if key not in seen:
                seen.add(key)
                groups_found += 1

    return groups_found
