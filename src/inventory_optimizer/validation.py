"""Validation of raw CSV frames. All row numbers refer to the file (header is row 1)."""

from __future__ import annotations

import numpy as np
import pandas as pd

SALES_REQUIRED = ("date", "sku", "quantity")
INVENTORY_REQUIRED = ("sku", "supplier", "unit_cost", "on_hand", "lead_time_days")


class DataError(Exception):
    """Raised when input files contain problems that prevent analysis.

    Attributes:
        problems: Human-readable problem descriptions with row numbers.
    """

    def __init__(self, problems: list[str]) -> None:
        super().__init__("; ".join(problems))
        self.problems = problems


def _flag(mask: pd.Series, errors: list[str], name: str, template: str, values: pd.Series) -> None:
    for idx in mask[mask].index:
        errors.append(f"{name} row {idx + 2}: " + template.format(value=values[idx]))


def _numeric(
    raw: pd.DataFrame,
    col: str,
    name: str,
    errors: list[str],
    *,
    minimum: float,
    strict: bool,
    default: float | None,
) -> pd.Series:
    """Parse a numeric column; ``default=None`` marks the column as required."""
    text = raw[col].str.strip()
    blank = text == ""
    num = pd.to_numeric(text.where(~blank), errors="coerce")
    finite = pd.Series(np.isfinite(num), index=num.index)
    _flag(~blank & ~finite, errors, name, col + " {value!r} is not a number", text)
    bad_range = finite & ((num <= minimum) if strict else (num < minimum))
    bound = "greater than" if strict else "at least"
    _flag(bad_range, errors, name, f"{col} {{value!r}} must be {bound} {minimum:g}", text)
    if default is None:
        _flag(blank, errors, name, col + " is required", text)
        return num
    return num.fillna(default)


def _check_columns(raw: pd.DataFrame, required: tuple[str, ...], name: str, errors: list[str]) -> bool:
    if raw.empty:
        errors.append(f"{name}: file has no data rows")
        return False
    missing = [c for c in required if c not in raw.columns]
    if missing:
        errors.append(f"{name}: missing required column(s): {', '.join(missing)}")
    return not missing


def validate_sales(raw: pd.DataFrame, name: str = "sales.csv") -> tuple[pd.DataFrame, list[str]]:
    """Validate and convert a raw (all-string) sales frame.

    Args:
        raw: Frame read with ``dtype=str``.
        name: File name used in messages.

    Returns:
        The typed frame (date, sku, quantity) and a list of error messages.
    """
    errors: list[str] = []
    if not _check_columns(raw, SALES_REQUIRED, name, errors):
        return pd.DataFrame(), errors
    dates = pd.to_datetime(raw["date"].str.strip(), format="%Y-%m-%d", errors="coerce")
    _flag(dates.isna(), errors, name, "date {value!r} is not a valid YYYY-MM-DD date", raw["date"])
    sku = raw["sku"].str.strip()
    _flag(sku == "", errors, name, "sku is empty", sku)
    qty = _numeric(raw, "quantity", name, errors, minimum=0, strict=False, default=None)
    return pd.DataFrame({"date": dates, "sku": sku, "quantity": qty.astype(float)}), errors


def validate_inventory(
    raw: pd.DataFrame, name: str = "inventory.csv"
) -> tuple[pd.DataFrame, list[str]]:
    """Validate and convert a raw (all-string) inventory frame.

    Args:
        raw: Frame read with ``dtype=str``.
        name: File name used in messages.

    Returns:
        The typed frame with defaults applied and a list of error messages.
    """
    errors: list[str] = []
    if not _check_columns(raw, INVENTORY_REQUIRED, name, errors):
        return pd.DataFrame(), errors
    sku = raw["sku"].str.strip()
    supplier = raw["supplier"].str.strip()
    _flag(sku == "", errors, name, "sku is empty", sku)
    _flag(supplier == "", errors, name, "supplier is empty", supplier)
    _flag((sku != "") & sku.duplicated(keep="first"), errors, name, "duplicate sku {value!r}", sku)

    def num(col: str, minimum: float, strict: bool, default: float | None) -> pd.Series:
        if col not in raw.columns:
            if default is None:
                return pd.Series(np.nan, index=raw.index)
            return pd.Series(default, index=raw.index, dtype=float)
        return _numeric(raw, col, name, errors, minimum=minimum, strict=strict, default=default)

    def text(col: str, default: str) -> pd.Series:
        if col not in raw.columns:
            return pd.Series(default, index=raw.index)
        values = raw[col].str.strip()
        return values.where(values != "", default)

    frame = pd.DataFrame(
        {
            "sku": sku,
            "description": text("description", ""),
            "category": text("category", "Uncategorized"),
            "supplier": supplier,
            "unit_cost": num("unit_cost", 0, True, None),
            "on_hand": num("on_hand", 0, False, None),
            "on_order": num("on_order", 0, False, 0.0),
            "lead_time_days": num("lead_time_days", 0, True, None),
            "lead_time_std_days": num("lead_time_std_days", 0, False, 0.0),
            "moq": num("moq", 0, True, 1.0),
            "case_pack": num("case_pack", 0, True, 1.0),
            "order_cost": num("order_cost", 0, False, float("nan")),
        }
    )
    return frame, errors
