"""Deterministic synthetic data generator."""

from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path

import numpy as np
import pandas as pd

END_DATE = date(2026, 6, 30)
SUPPLIERS = [
    "Acme Wholesale", "Nordic Supply Co", "Delta/Gamma Imports", "Blue River Trading",
    "Summit Distribution", "Harbor Goods", "Pioneer Parts", "Greenfield Foods",
]  # fmt: skip
CATEGORIES = ["Beverages", "Snacks", "Household", "Personal care", "Pet", "Stationery"]
PATTERNS = ("steady", "seasonal", "intermittent", "fast", "dead")
PATTERN_WEIGHTS = (0.40, 0.20, 0.20, 0.10, 0.10)


def _daily_demand(rng: np.random.Generator, pattern: str, days: int, base: float) -> np.ndarray:
    t = np.arange(days)
    if pattern == "seasonal":
        rate = base * (1 + 0.7 * np.sin(2 * np.pi * t / 365 + rng.uniform(0, 6.28)))
        return rng.poisson(np.maximum(rate, 0.05)).astype(float)
    if pattern == "intermittent":
        sold = rng.random(days) < 0.12
        return np.where(sold, rng.integers(1, 6, days), 0).astype(float)
    if pattern == "fast":
        return rng.poisson(base * 4, days).astype(float)
    if pattern == "dead":
        active = days // 10 + 1
        return np.where(t < active, rng.poisson(base, days), 0).astype(float)
    return rng.poisson(base, days).astype(float)


def generate(skus: int = 200, days: int = 365, seed: int = 42) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Generate realistic synthetic sales and inventory tables.

    Args:
        skus: Number of SKUs.
        days: Days of sales history ending at 2026-06-30.
        seed: Random seed; the same seed always gives the same data.

    Returns:
        A ``(sales, inventory)`` pair of frames matching the CSV formats.
    """
    rng = np.random.default_rng(seed)
    start = END_DATE - timedelta(days=days - 1)
    dates = pd.date_range(start, END_DATE, freq="D")
    kinds = rng.choice(PATTERNS, size=skus, p=PATTERN_WEIGHTS)
    sale_parts: list[pd.DataFrame] = []
    inv_rows: list[dict[str, object]] = []
    for i, kind in enumerate(kinds):
        sku = f"SKU-{i + 1:04d}"
        base = float(rng.choice([0.6, 1.5, 3.0, 6.0]))
        series = _daily_demand(rng, str(kind), days, base)
        hit = series > 0
        sale_parts.append(pd.DataFrame({"date": dates[hit], "sku": sku, "quantity": series[hit]}))
        recent = float(series[-90:].mean())
        lead = float(rng.integers(3, 22))
        cost = round(float(rng.lognormal(2.3, 0.7)), 2)
        cover_factor = float(rng.choice([0.3, 0.6, 1.5, 3.0, 6.0, 12.0], p=[0.07, 0.06, 0.27, 0.3, 0.2, 0.1]))
        on_hand = float(np.floor(max(recent, 0.2) * lead * cover_factor))
        if kind == "dead":
            on_hand = float(rng.integers(20, 200))
        category = CATEGORIES[i % len(CATEGORIES)]
        inv_rows.append(
            {
                "sku": sku,
                "description": f"{category} item {i + 1}",
                "category": category,
                "supplier": SUPPLIERS[int(rng.integers(0, len(SUPPLIERS)))],
                "unit_cost": cost,
                "on_hand": on_hand,
                "on_order": float(rng.choice([0, 0, 0, 24, 48])),
                "lead_time_days": lead,
                "lead_time_std_days": float(rng.choice([0, 1, 2])),
                "moq": float(rng.choice([1, 6, 12, 24])),
                "case_pack": float(rng.choice([1, 6, 12])),
                "order_cost": float(rng.choice([25, 50, 75])),
            }
        )
    sales = pd.concat(sale_parts, ignore_index=True)
    sales["date"] = sales["date"].dt.strftime("%Y-%m-%d")
    sales = sales.sort_values(["date", "sku"], kind="mergesort").reset_index(drop=True)
    return sales, pd.DataFrame(inv_rows)


def write_sample(directory: str | Path, skus: int = 200, days: int = 365, seed: int = 42) -> list[Path]:
    """Write ``sales.csv`` and ``inventory.csv`` to a folder.

    Args:
        directory: Destination folder (created if needed).
        skus: Number of SKUs.
        days: Days of history.
        seed: Random seed.

    Returns:
        The two paths written.
    """
    out = Path(directory)
    out.mkdir(parents=True, exist_ok=True)
    sales, inventory = generate(skus, days, seed)
    paths = [out / "sales.csv", out / "inventory.csv"]
    sales.to_csv(paths[0], index=False, lineterminator="\n")
    inventory.to_csv(paths[1], index=False, lineterminator="\n")
    return paths
