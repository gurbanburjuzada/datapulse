"""
distribution_profiler.py

Profiles the distribution shape of each column:
  - Numeric: mean, median, std, skewness, kurtosis
  - Categorical: top value counts, imbalance flag

Skewness and kurtosis are core ML theory — skewed features hurt
linear models and naive Bayes; heavy-tailed distributions mislead
mean/std-based normalisation.
"""

import pandas as pd
import numpy as np
from scipy import stats as scipy_stats
import logging
import time
from agent.state import (
    DistributionInfo, DistributionResult, Severity, Finding
)
log = logging.getLogger("datapulse.distribution")


def run_distribution_profiler(df: pd.DataFrame) -> DistributionResult:
    log.debug("  distribution_profiler: START")
    t = time.perf_counter()
    distributions: list[DistributionInfo] = []
    findings: list[Finding] = []

    for col in df.columns:
        log.debug("  distribution_profiler: processing column '%s'", col)
        series = df[col].dropna()
        if pd.api.types.is_numeric_dtype(series):
            _profile_numeric(col, series, distributions, findings)
        else:
            _profile_categorical(col, series, distributions, findings)
    log.debug("  distribution_profiler: END (%.3fs)", time.perf_counter() - t)

    return DistributionResult(
        distributions=distributions,
        findings=findings
    )


def _profile_numeric(
        col: str,
        series: pd.Series,
        distributions: list[DistributionInfo],
        findings: list[Finding]
) -> None:
    if len(series) < 3:
        return
    mean = float(series.mean())
    median = float(series.median())
    std = float(series.std())
    skewness = float(scipy_stats.skew(series))
    kurt = float(scipy_stats.kurtosis(series))

    distributions.append(DistributionInfo(
        column=col,
        mean=round(mean, 4),
        median=round(median, 4),
        std=round(std, 4),
        skewness=round(skewness, 4),
        kurtosis=round(kurt, 4)
    ))

    # ── Skewness findings ─────────────────────────────────────────────────
    abs_skew = abs(skewness)
    direction = "right (positive)" if skewness > 0 else "left (negative)"

    if abs_skew > 2:
        findings.append(Finding(
            severity=Severity.WARNING,
            column=col,
            title=f"High skewness in '{col}'",
            detail=(
                f"Skewness = {skewness:.2f} ({direction}). "
                f"Mean ({mean:.2f}) and median ({median:.2f}) diverge, "
                f"suggesting a long tail."
            ),
            recommendation=(
                "Apply a log1p transform (if all values ≥ 0), Box-Cox, or "
                "Yeo-Johnson transformation before fitting models that assume "
                "normality. Tree-based models (XGBoost, Random Forest) are "
                "robust to skew and may not need this."
            )
        ))

    elif abs_skew > 0.5:
        findings.append(Finding(
            severity=Severity.INFO,
            column=col,
            title=f"Moderate skewness in '{col}'",
            detail=f"Skewness = {skewness:.2f} ({direction}).",
            recommendation=(
                "Mild skew is generally fine, but consider transforming if,"
                "using a linear model or logistic regression."
            )
        ))

    # ── Kurtosis findings ─────────────────────────────────────────────────
    if kurt > 3:
        findings.append(Finding(
            severity=Severity.INFO,
            column=col,
            title=f"Heavy-tailed distribution in '{col}'",
            detail=(
                f"Excess kurtosis = {kurt:.2f} (leptokurtic). "
                "More extreme values than a normal distribution."
            ),
            recommendation=(
                "Heavy tails amplify outlier impact in linear models. "
                "Consider robust loss functions or outlier clipping."
            )
        ))


def _profile_categorical(
        col: str,
        series: pd.Series,
        distributions: list[DistributionInfo],
        findings: list[Finding]
) -> None:
    value_counts = series.value_counts()
    top_values = [
        {"val": str(val), "count": int(cnt)}
        for val, cnt in value_counts.head(10).items()
    ]

    total = len(series)
    top_count = int(value_counts.iloc[0]) if len(value_counts) > 0 else 0.0
    top_pct = round(top_count / total * 100, 2) if total > 0 else 0.0

    # Heuristic: flag imbalance if top class > 80% and there are only 2-10 classes
    n_classes = len(value_counts)
    is_imbalanced = (top_pct > 80) and (2 <= n_classes <= 10)

    distributions.append(DistributionInfo(
        column=col,
        top_values=top_values,
        is_imbalanced=is_imbalanced
    ))

    # ── Findings ──────────────────────────────────────────────────────────
    if is_imbalanced:
        findings.append(Finding(
            severity=Severity.WARNING,
            column=col,
            title=f"Class imbalance in '{col}'",
            detail=(
                f"The most common value ('{value_counts.index[0]}') "
                f"appears in {top_pct:.1f}% of rows. "
                f"There are {n_classes} distinct classes."
            ),
            recommendation=(
                "If this is a target column, use stratified train/test split and "
                "consider class-weighting (class_weight='balanced'), SMOTE, or "
                "adjusting decision thresholds. Accuracy alone is misleading here — "
                "use F1, precision-recall, or ROC-AUC."
            )
        ))

    if n_classes == 1:
        findings.append(Finding(
            severity=Severity.CRITICAL,
            column=col,
            title=f"Single-value categorical column '{col}'",
            detail=f"All non-null rows share the same value: '{value_counts.index[0]}'.",
            recommendation="Drop this column — it is constant and carries no information."
        ))
