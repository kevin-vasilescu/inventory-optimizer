"""CSV loading."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import pandas as pd

from .validation import DataError, validate_inventory, validate_sales


def _read_raw(path: Path) -> tuple[pd.DataFrame | None, list[str]]:
    try:
        raw = pd.read_csv(path, dtype=str, keep_default_na=False, encoding="utf-8-sig")
    except FileNotFoundError:
        return None, [f"{path.name}: file not found ({path})"]
    except pd.errors.EmptyDataError:
        return None, [f"{path.name}: file is empty"]
    except (pd.errors.ParserError, UnicodeDecodeError, IsADirectoryError, PermissionError) as exc:
        return None, [f"{path.name}: cannot read file ({exc})"]
    raw.columns = pd.Index([str(c).strip().lower() for c in raw.columns])
    return raw, []


def _read(
    path: str | Path, check: Callable[[pd.DataFrame, str], tuple[pd.DataFrame, list[str]]]
) -> tuple[pd.DataFrame | None, list[str]]:
    p = Path(path)
    raw, errors = _read_raw(p)
    if raw is None:
        return None, errors
    frame, errors = check(raw, p.name)
    return (None if errors else frame), errors


def read_sales(path: str | Path) -> tuple[pd.DataFrame | None, list[str]]:
    """Read and validate a sales CSV without raising.

    Args:
        path: Path to ``sales.csv``.

    Returns:
        The typed frame (``None`` if invalid) and the list of problems.
    """
    return _read(path, validate_sales)


def read_inventory(path: str | Path) -> tuple[pd.DataFrame | None, list[str]]:
    """Read and validate an inventory CSV without raising.

    Args:
        path: Path to ``inventory.csv``.

    Returns:
        The typed frame (``None`` if invalid) and the list of problems.
    """
    return _read(path, validate_inventory)


def load_sales(path: str | Path) -> pd.DataFrame:
    """Load a sales CSV.

    Args:
        path: Path to ``sales.csv`` with columns date, sku, quantity.

    Returns:
        A frame with columns ``date`` (datetime64), ``sku`` and ``quantity``.

    Raises:
        DataError: If the file is missing or invalid.
    """
    frame, errors = read_sales(path)
    if frame is None:
        raise DataError(errors)
    return frame


def load_inventory(path: str | Path) -> pd.DataFrame:
    """Load an inventory CSV and apply column defaults.

    Args:
        path: Path to ``inventory.csv``.

    Returns:
        A frame with one row per SKU and all documented columns.

    Raises:
        DataError: If the file is missing or invalid.
    """
    frame, errors = read_inventory(path)
    if frame is None:
        raise DataError(errors)
    return frame
