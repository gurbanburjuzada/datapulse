"""
correlation_mapper.py

Computes Pearson correlation between all numeric column pairs and:
  - Returns the full matrix as heatmap-ready JSON for the frontend
  - Flags highly correlated pairs (|r| > 0.85) as potential
    multicollinearity problems
  - Flags suspicious perfect correlations (|r| > 0.99) as likely
    data leakage or derived columns

Pearson r is appropriate for linear relationships between continuous
variables. For ordinal or non-linear relationships, Spearman would
be better — noted in recommendations.
"""
import time
import pandas as pd
import numpy as np
import logging
from agent.state import (
    CorrelationPair, CorrelationResult, Severity, Finding
)

log = logging.getLogger("datapulse.correlation")
HIGH_CORR_THRESHOLD = 0.85
PERFECT_CORR_THRESHOLD = 0.99


def run_correlation_mapper(df: pd.DataFrame) -> CorrelationResult:
    log.debug("  correlation_mapper: START")
    t = time.perf_counter()

    numeric_df = df.select_dtypes(include=[np.number])
    findings: list[Finding] = []
    all_pairs: list[CorrelationPair] = []
    high_pairs: list[CorrelationPair] = []

    # Need at least 2 numeric columns for correlations to make sense
    if len(numeric_df.columns) < 2:
        return CorrelationResult(
            pairs=[],
            high_corr_pairs=[],
            heatmap_data={},
            findings=[Finding(
                severity=Severity.INFO,
                column=None,
                title="Correlation analysis skipped",
                detail="Dataset has  fewer than 2 numeric columns.",
                recommendation="No action needed."
            )]
        )

    log.debug("  correlation_mapper: computing corr matrix")
    corr_matrix = numeric_df.corr(method="pearson")
    cols = corr_matrix.columns.tolist()
    log.debug("  correlation_mapper: corr matrix done")

    # ── Build pair list (upper triangle only, no self-correlations) ───────
    for i, col_a in enumerate(cols):
        for j, col_b in enumerate(cols):
            if j <= i:
                continue
            r = corr_matrix.loc[col_a, col_b]
            if pd.isna(r):
                continue
            pair = CorrelationPair(
                col_a=col_a,
                col_b=col_b,
                pearson_r=round(float(r), 4),
                abs_r=round(abs(float(r)), 4)
            )
            all_pairs.append(pair)
            if pair.abs_r >= HIGH_CORR_THRESHOLD:
                high_pairs.append(pair)

    all_pairs.sort(key= lambda p: p.abs_r, reverse=True)
    high_pairs.sort(key=lambda p: p.abs_r, reverse=True)

    # ── Heatmap data for the frontend ────────────────────────────────────
    matrix_values = corr_matrix.values.tolist()
    # Replace NaN with None so JSON serialisation works
    matrix_clean = [
        [None if (isinstance(v, float) and np.isnan(v)) else round(v, 4) for v in row]
        for row in matrix_values
    ]
    heatmap_data = {
        "columns": cols,
        "matrix": matrix_clean
    }

    # ── Findings ──────────────────────────────────────────────────────────
    for pair in high_pairs:
        if pair.abs_r >= PERFECT_CORR_THRESHOLD:
            findings.append(Finding(
                severity=Severity.CRITICAL,
                column=None,
                title=f"Near-perfect correlation: '{pair.col_a}' ↔ '{pair.col_b}'",
                detail=(
                    f"Pearson r = {pair.pearson_r:.3f}. One column may be derived "
                    "from the other, or both may encode the same underlying quantity."
                ),
                recommendation=(
                    "Check whether one column is a direct transform of the other "
                    "(e.g. price vs price_in_cents, age vs birth_year). "
                    "Keeping both in a model causes severe multi-collinearity. "
                    "If this is a target-derived column, it is data leakage — drop it immediately."
                )
            ))
        else:
            findings.append(Finding(
                severity=Severity.WARNING,
                column=None,
                title=f"High Correlation: '{pair.col_a}' ↔ {pair.col_b}",
                detail=f"Pearson r = {pair.pearson_r:.3f} (|r| > {HIGH_CORR_THRESHOLD}).",
                recommendation=(
                    "High correlation between features can cause multi-collinearity "
                    "in linear models, inflating coefficient variance. "
                    "Consider dropping one, using PCA, or using regularisation (Ridge/Lasso). "
                    "Tree-based models are naturally robust to this."
                )
            ))

    if not findings and len(all_pairs) > 0:
        findings.append(Finding(
            severity=Severity.INFO,
            column=None,
            title="No high-correlation pairs found",
            detail=f"All {len(all_pairs)} numeric column pair(s) have |r| < {HIGH_CORR_THRESHOLD}.",
            recommendation="Correlation structure looks healthy for linear modelling."
        ))
    log.debug("  correlation_mapper: END (%.3fs)", time.perf_counter() - t)

    return CorrelationResult(
        pairs=all_pairs,
        high_corr_pairs=high_pairs,
        heatmap_data=heatmap_data,
        findings=findings
    )
