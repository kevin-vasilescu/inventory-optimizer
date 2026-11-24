"""Demand statistics over the lookback window."""

from __future__ import annotations

from datetime import date, timedelta

import numpy as np
import pandas as pd


def window_start(as_of: date, lookback_days: int) -> date:
    """First day of the inclusive lookback window.

    Args:
        as_of: Last day of the window.
        lookback_days: Window length in days.

    Returns:
        The first date in the window.
    """
    return as_of - timedelta(days=lookback_days - 1)


def daily_matrix(
    sales: pd.DataFrame, skus: list[str], as_of: date, lookback_days: int
) -> pd.DataFrame:
    """Build a complete day-by-SKU demand matrix, filling missing days with 0.

    Args:
        sales: Frame with date, sku, quantity.
        skus: SKUs to include (columns of the result).
        as_of: Last day of the window.
        lookback_days: Window length in days.

    Returns:
        Frame indexed by every day in the window with one column per SKU.
    """
    days = pd.date_range(window_start(as_of, lookback_days), as_of, freq="D")
    empty = pd.DataFrame(0.0, index=days, columns=pd.Index(skus))
    mask = (
        (sales["date"] >= days[0]) & (sales["date"] <= days[-1]) & sales["sku"].isin(skus)
    )
    inside = sales[mask]
    if inside.empty:
        return empty
    daily = inside.groupby(["date", "sku"])["quantity"].sum().unstack(fill_value=0.0)
    return daily.reindex(index=days, columns=pd.Index(skus), fill_value=0.0).astype(float)


def demand_stats(matrix: pd.DataFrame) -> pd.DataFrame:
    """Average and sample standard deviation (ddof=1) of daily demand.

    Args:
        matrix: Output of :func:`daily_matrix`.

    Returns:
        Frame indexed by SKU with ``avg_daily_demand`` and ``demand_std_daily``.
    """
    return pd.DataFrame(
        {
            "avg_daily_demand": matrix.mean(),
            "demand_std_daily": matrix.std(ddof=1).fillna(0.0),
        }
    )


def weekly_cv(matrix: pd.DataFrame) -> pd.Series:
    """Coefficient of variation of weekly demand.

    Days are summed into 7-day buckets ending at the last row; an incomplete
    leading bucket is dropped. The standard deviation uses ddof=1 (0 for a single
    bucket). SKUs with zero mean weekly demand, or windows shorter than a week,
    get NaN.

    Args:
        matrix: Output of :func:`daily_matrix`.

    Returns:
        Series indexed by SKU.
    """
    weeks = len(matrix) // 7
    if weeks == 0:
        return pd.Series(np.nan, index=matrix.columns, dtype=float)
    tail = matrix.iloc[len(matrix) - weeks * 7 :]
    weekly = tail.groupby(np.arange(len(tail)) // 7).sum()
    mean = weekly.mean()
    std = weekly.std(ddof=1).fillna(0.0)
    return (std / mean.where(mean > 0)).astype(float)
