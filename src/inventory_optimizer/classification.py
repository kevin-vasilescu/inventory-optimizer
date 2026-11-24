"""ABC and XYZ classification."""

from __future__ import annotations

import numpy as np
import pandas as pd

_EPS = 1e-9


def classify_abc(consumption: pd.Series, thresholds: tuple[float, float] = (0.80, 0.95)) -> pd.Series:
    """Classify SKUs by cumulative share of consumption value.

    Ties are broken by SKU (ascending). Zero consumption is always class C.

    Args:
        consumption: Consumption value indexed by SKU.
        thresholds: Cumulative share cutoffs for A and B (inclusive).

    Returns:
        Series of "A", "B" or "C" with the original index.
    """
    ordered = (
        consumption.rename_axis("sku")
        .reset_index(name="value")
        .sort_values(["value", "sku"], ascending=[False, True], kind="mergesort")
    )
    total = float(ordered["value"].sum())
    if total <= 0:
        return pd.Series("C", index=consumption.index)
    share = ordered["value"].cumsum() / total
    a, b = thresholds
    labels = np.select([share <= a + _EPS, share <= b + _EPS], ["A", "B"], default="C")
    labels = np.where(ordered["value"] <= 0, "C", labels)
    return pd.Series(labels, index=ordered["sku"].to_numpy()).reindex(consumption.index)


def classify_xyz(cv: pd.Series, thresholds: tuple[float, float] = (0.5, 1.0)) -> pd.Series:
    """Classify SKUs by coefficient of variation of weekly demand.

    Args:
        cv: Coefficient of variation indexed by SKU; NaN means no demand.
        thresholds: CV cutoffs for X and Y (inclusive).

    Returns:
        Series of "X", "Y" or "Z"; NaN input becomes "Z".
    """
    x, y = thresholds
    labels = np.select([cv <= x, cv <= y], ["X", "Y"], default="Z")
    return pd.Series(labels, index=cv.index)
