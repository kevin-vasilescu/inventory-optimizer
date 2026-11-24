"""Conversion of result frames into clean, null-safe export structures."""

from __future__ import annotations

import json
from datetime import date
from typing import TYPE_CHECKING, Any

import pandas as pd

if TYPE_CHECKING:
    from ..models import AnalysisResult


def _clean(value: Any) -> Any:
    if value is None or (not isinstance(value, (str, date)) and pd.isna(value)):
        return None
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, bool) or isinstance(value, str):
        return value
    number = float(value)
    return int(number) if number.is_integer() else round(number, 4)


def export_frame(frame: pd.DataFrame) -> pd.DataFrame:
    """Return an object-typed copy with None for undefined values and ISO dates.

    Args:
        frame: Any result frame.

    Returns:
        A frame where integral numbers are ints and others are rounded to 4 places.
    """
    out = pd.DataFrame(
        {col: [_clean(v) for v in frame[col].tolist()] for col in frame.columns},
        dtype=object,
    )
    return out


def records(frame: pd.DataFrame) -> list[dict[str, Any]]:
    """Convert a frame to a list of JSON-safe dicts.

    Args:
        frame: Any result frame.

    Returns:
        One dict per row.
    """
    cleaned = export_frame(frame)
    return [{str(k): v for k, v in row.items()} for row in cleaned.to_dict(orient="records")]


def to_json(result: AnalysisResult) -> str:
    """Serialise a result as JSON.

    Args:
        result: The analysis result.

    Returns:
        Indented JSON with keys as_of, config, summary, warnings and skus.
    """
    cfg = result.config
    payload = {
        "as_of": result.as_of.isoformat(),
        "config": {
            "lookback_days": cfg.lookback_days,
            "service_level": cfg.service_level,
            "holding_cost_rate": cfg.holding_cost_rate,
            "default_order_cost": cfg.default_order_cost,
            "abc_thresholds": list(cfg.abc_thresholds),
            "xyz_thresholds": list(cfg.xyz_thresholds),
            "dead_stock_days": cfg.dead_stock_days,
            "overstock_days": cfg.overstock_days,
        },
        "summary": result.summary(),
        "warnings": result.warnings,
        "skus": records(result.frame),
    }
    return json.dumps(payload, indent=2, allow_nan=False)
