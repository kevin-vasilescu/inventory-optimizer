"""Markdown report."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pandas as pd

from .data import export_frame

if TYPE_CHECKING:
    from ..models import AnalysisResult

URGENT_ROWS = 15
URGENT_COLUMNS = ["sku", "supplier", "status", "on_hand", "reorder_point", "days_of_cover", "recommended_order_qty", "order_value"]
PLAN_TABLE_COLUMNS = ["sku", "supplier", "status", "abc_class", "xyz_class", "inventory_position", "reorder_point", "eoq", "recommended_order_qty", "unit_cost", "order_value", "expected_arrival"]


def money(value: float) -> str:
    """Format a currency-like number with thousands separators.

    Args:
        value: The number.

    Returns:
        Text such as ``1,234.50``.
    """
    return f"{value:,.2f}"


def _cell(value: object) -> str:
    if value is None:
        return "-"
    if isinstance(value, float):
        return f"{value:,.2f}"
    return str(value).replace("|", "\\|")


def md_table(frame: pd.DataFrame, columns: list[str]) -> str:
    """Render selected columns as a GitHub-flavoured Markdown table.

    Args:
        frame: Source frame.
        columns: Columns to include, in order.

    Returns:
        Table text; undefined values appear as ``-``.
    """
    clean = export_frame(frame[columns])
    lines = ["| " + " | ".join(columns) + " |", "|" + "|".join("---" for _ in columns) + "|"]
    for row in clean.itertuples(index=False):
        lines.append("| " + " | ".join(_cell(v) for v in row) + " |")
    return "\n".join(lines)


def render(result: AnalysisResult) -> str:
    """Render the Markdown report.

    Args:
        result: The analysis result.

    Returns:
        Markdown with summary, KPIs, ABC x XYZ matrix, urgent SKUs and the full plan.
    """
    s = result.summary()
    cfg = result.config
    kpis = [
        ("SKUs analysed", str(s["sku_count"])),
        ("Inventory value", money(s["inventory_value"])),
        ("Dead-stock value", money(s["dead_stock_value"])),
        ("Overstock value", money(s["overstock_value"])),
        ("Capital needed for recommended orders", money(s["capital_needed"])),
        *((f"Status {k}", str(v)) for k, v in s["status_counts"].items()),
    ]
    parts = [
        "# Inventory optimization report",
        f"As of {s['as_of']} | lookback {cfg.lookback_days} days | service level {cfg.service_level:g} | holding cost rate {cfg.holding_cost_rate:g}",
        "## Key figures",
        "| Metric | Value |\n|---|---|\n" + "\n".join(f"| {k} | {v} |" for k, v in kpis),
        "## ABC x XYZ matrix (SKU counts)",
        "| ABC \\ XYZ | X | Y | Z |\n|---|---|---|---|\n"
        + "\n".join(f"| {a} | " + " | ".join(str(s["abc_xyz"][a][x]) for x in "XYZ") + " |" for a in "ABC"),
    ]
    plan = result.reorder_plan()
    parts.append(f"## Most urgent SKUs (top {URGENT_ROWS})")
    parts.append(md_table(plan.head(URGENT_ROWS), URGENT_COLUMNS) if len(plan) else "No SKU needs ordering.")
    parts.append("## Full reorder plan")
    full = result.frame.sort_values("sku")
    full = full[full["recommended_order_qty"] > 0]
    parts.append(md_table(full, PLAN_TABLE_COLUMNS) if len(full) else "No SKU needs ordering.")
    if result.warnings:
        parts.append("## Warnings\n" + "\n".join(f"- {w}" for w in result.warnings))
    return "\n\n".join(parts) + "\n"
