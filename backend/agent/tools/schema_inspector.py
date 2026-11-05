"""
schema_inspector.py

Inspects the structural shape of the dataframe:
  - column names, dtypes
  - null counts and percentages
  - unique value counts (cardinality)
  - sample values for each column
  - generates Findings for high nulls, suspicious dtypes, zero-variance cols
"""

import pandas as pd
from agent.state import (
    ColumnMeta, SchemaResult, Finding, Severity
)
import logging
import time
log = logging.getLogger("datapulse.schema")


def run_schema_inspector(df: pd.DataFrame) -> SchemaResult:
    log.debug("  schema_inspector: START (%d rows × %d cols)", len(df), len(df.columns))
    t = time.perf_counter()
    row_count = len(df)
    col_count = len(df.columns)
    columns: list[ColumnMeta] = []
    findings: list[Finding] = []

    for col in df.columns:
        series = df[col]
        null_count = int(series.isna().sum())
        null_pct = round(null_count / row_count * 100, 2) if row_count else 0.0
        unique_count = int(series.nunique(dropna=True))
        cardinality_pct = round(unique_count / row_count * 100, 2) if row_count else 0.0

        # Show up to 5 UNIQUE non-null values so the sample is informative.
        # .head(5) would just show the first 5 rows which are often repetitive
        # (e.g. "Yes, No, No, Yes, No" hides the third distinct value).
        unique_sample = series.dropna().unique()[:5]
        sample_vals = [
            v if isinstance(v, (int, float, bool, str)) else str(v)
            for v in unique_sample.tolist()
        ]

        columns.append(ColumnMeta(
            name=col,
            dtype=str(series.dtype),
            null_count=null_count,
            null_pct=null_pct,
            unique_count=unique_count,
            cardinality_pct=cardinality_pct,
            sample_values=sample_vals
        ))

        # ── Findings ──────────────────────────────────────────────────────

        # High nulls
        if null_pct > 40:
            findings.append(Finding(
                severity=Severity.CRITICAL,
                column=col,
                title=f"High null rate in '{col}'",
                detail=f"{null_pct:.1f}% of values are missing ({null_count:,} rows).",
                recommendation=(
                    "Consider dropping this column if it exceeds 50% nulls, "
                    "or apply domain-appropriate imputation (median for numeric, "
                    "mode or a dedicated 'Unknown' category for categorical)."
                )
            ))

        elif null_pct > 5:
            findings.append(Finding(
                severity=Severity.WARNING,
                column=col,
                title=f"Moderate nulls in '{col}'",
                detail=f"{null_pct:.1f}% of values are missing ({null_count:,} rows).",
                recommendation=(
                    "Investigate whether missingness is random or systematic. "
                    "For ML, impute before modelling — do not rely on the model "
                    "to handle NaNs unless using tree-based methods with native support."
                )
            ))

        # Zero-variance (constant) column
        if unique_count <= 1:
            findings.append(Finding(
                severity=Severity.CRITICAL,
                column=col,
                title=f"Constant column {col}",
                detail=f"'{col}' has only {unique_count} unique value(s) across all rows.",
                recommendation=(
                    "Drop this column — it carries zero predictive signal and "
                    "will cause issues with variance-based feature selection and "
                    "some model types."
                )
            ))

        # Very low cardinality numeric (likely miscoded categorical)
        if str(series.dtype) in ("float64", "int64") and 2 <= unique_count <= 10:
            findings.append(Finding(
                severity=Severity.INFO,
                column=col,
                title=f"Low-cardinality numeric '{col}'",
                detail=(
                    f"'{col}' is stored as {series.dtype} but has only "
                    f"{unique_count} unique values: {sample_vals}."
                ),
                recommendation=(
                    "This column may be a categorical variable (e.g. a label or "
                    "flag) encoded as a number. Verify intent — if categorical, "
                    "cast to string or use one-hot encoding."
                )
            ))

        # Object column with very high cardinality (free text or ID leak)
        if str(series.dtype) == "object" and cardinality_pct > 80:
            findings.append(Finding(
                severity=Severity.WARNING,
                column=col,
                title=f"High-cardinality text column '{col}'",
                detail=(
                    f"'{col}' is a string column with {cardinality_pct:.1f}% "
                    f"unique values ({unique_count:,} distinct)."
                ),
                recommendation=(
                    "This is likely a free-text field or unique ID. "
                    "Drop it if it's an ID, or apply text-specific feature "
                    "extraction (TF-IDF, embeddings) if it's natural language."
                )
            ))

    # Dataset-level: no rows
    if row_count == 0:
        findings.append(Finding(
            severity=Severity.CRITICAL,
            column=None,
            title="Empty Dataset",
            detail="The uploaded file contains no data rows.",
            recommendation="Upload a non-empty file."
        ))
    log.debug("  schema_inspector: END (%.3fs)", time.perf_counter() - t)

    return SchemaResult(
        row_count=row_count,
        col_count=col_count,
        columns=columns,
        findings=findings
    )
