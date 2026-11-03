"""
outlier_detector.py

Runs two complementary outlier detection methods on every numeric column:
  - IQR (interquartile range) — robust to skewed distributions
  - Z-score — assumes approximate normality, threshold |z| > 3

Both are classical statistics methods. Using both gives a richer picture:
IQR catches local outliers, z-score catches global extremes.
"""
import time
import pandas as pd
import numpy as np
import logging
from scipy import stats as scipy_stats

from agent.state import (
    OutlierInfo, OutlierResult, Severity, Finding
)
log = logging.getLogger("datapulse.outliers")


def run_outlier_detector(df: pd.DataFrame) -> OutlierResult:
    log.debug("  outlier_detector: START")
    t = time.perf_counter()
    numeric_cols = df.select_dtypes(include=[np.number]).columns.tolist()
    outlier_infos: list[OutlierInfo] = []
    findings: list[Finding] = []

    for col in numeric_cols:
        log.debug("  outlier_detector: processing column '%s'", col)
        series = df[col].dropna()
        if len(series) < 10:
            # too few values to make outlier claims
            continue

        # ── IQR method ───────────────────────────────────────────────────
        q1 = float(series.quantile(0.25))
        q3 = float(series.quantile(0.75))
        iqr = q3 - q1
        lower = q1 - 1.5 * iqr
        upper = q3 + 1.5 * iqr
        iqr_mask = (series < lower) | (series > upper)
        iqr_count = int(iqr_mask.sum())
        iqr_pct = round(iqr_count / len(series) * 100, 2)

        # ── Z-score method ───────────────────────────────────────────────
        z_scores = np.abs(scipy_stats.zscore(series))
        zscore_mask = z_scores > 3
        zscore_count = int(zscore_mask.sum())
        zscore_pct = round(zscore_count / len(series) * 100, 2)

        outlier_infos.append(OutlierInfo(
            column=col,
            iqr_outlier_count=iqr_count,
            zscore_outlier_count=zscore_count,
            iqr_outlier_pct=iqr_pct,
            zscore_outlier_pct=zscore_pct,
            lower_bound=round(lower, 4),
            upper_bound=round(upper, 4)
        ))

        # ── Findings ──────────────────────────────────────────────────────
        if iqr_count > 10:
            findings.append(Finding(
                severity=Severity.CRITICAL,
                column=col,
                title=f"Severe outliers in '{col}'",
                detail=(
                    f"{iqr_pct:.1f}% of values ({iqr_count:,}) fall outside the "
                    f"IQR bounds [{lower:.2f}, {upper:.2f}]."
                ),
                recommendation=(
                    "Investigate whether these are data-entry errors, legitimate "
                    "extremes, or a different population. Options: cap with "
                    "Winsorisation, apply log/Box-Cox transform, or model them "
                    "separately. Never silently drop without understanding the cause."
                )
            ))

        elif iqr_count > 3:
            findings.append(Finding(
                severity=Severity.WARNING,
                column=col,
                title=f"Moderate outliers in '{col}'",
                detail=(
                    f"{iqr_pct:.1f}% of values ({iqr_count:,}) fall outside the "
                    f"IQR bounds [{lower:.2f}, {upper:.2f}]."
                ),
                recommendation=(
                    "Review these values with a boxplot. If the model is sensitive "
                    "to scale (linear regression, SVM, KNN), consider Winsorisation "
                    "or robust scaling (RobustScaler) instead of StandardScaler."
                )
            ))

        # z-score finding only if it disagrees meaningfully with IQR
        # (IQR says fine but z-score finds extreme global outliers)

        if zscore_pct > 0 and iqr_pct < 3:
            findings.append(Finding(
                severity=Severity.INFO,
                column=col,
                title=f"Potential extreme values in '{col}' (z_score)",
                detail=(
                    f"{zscore_count} value(s) have |z| > 3 — statistically "
                    f"very far from the mean, even though IQR looks clean."
                ),
                recommendation=(
                    "These may be legitimate rare events. Check whether they "
                    "correspond to real-world extremes or are data errors."
                )
            ))
    log.debug("  outlier_detector: END (%.3fs)", time.perf_counter() - t)

    return OutlierResult(
        outlier_columns=outlier_infos,
        findings=findings
    )
