"""Self-contained HTML report."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any

import pandas as pd
from jinja2 import Environment, FileSystemLoader, select_autoescape

from .charts import PALETTE, bar_chart
from .data import export_frame
from .markdown import money

if TYPE_CHECKING:
    from ..models import AnalysisResult

TABLE_COLUMNS = [
    ("sku", "SKU"),
    ("supplier", "Supplier"),
    ("status", "Status"),
    ("abc_class", "ABC"),
    ("xyz_class", "XYZ"),
    ("on_hand", "On hand"),
    ("inventory_position", "Position"),
    ("reorder_point", "Reorder pt"),
    ("days_of_cover", "Cover (d)"),
    ("recommended_order_qty", "Order qty"),
    ("order_value", "Order value"),
    ("expected_arrival", "Arrival"),
]
HEAT = (37, 99, 235)


def _fmt(value: object) -> str:
    if value is None:
        return "-"
    if isinstance(value, float):
        return f"{value:,.2f}"
    if isinstance(value, int):
        return f"{value:,}"
    return str(value)


def _heat_style(count: int, top: int) -> str:
    alpha = 0.08 + 0.72 * (count / top if top else 0)
    r, g, b = HEAT
    text = "#ffffff" if alpha > 0.5 else "#0f172a"
    return f"background:rgba({r},{g},{b},{alpha:.2f});color:{text}"


def _rows(frame: pd.DataFrame) -> list[list[str]]:
    clean = export_frame(frame[[c for c, _ in TABLE_COLUMNS]])
    return [[_fmt(v) for v in row] for row in clean.itertuples(index=False)]


def _context(result: AnalysisResult) -> dict[str, Any]:
    s = result.summary()
    frame = result.frame
    matrix = s["abc_xyz"]
    top = max((n for row in matrix.values() for n in row.values()), default=0)
    heat = [
        {"label": a, "cells": [{"n": matrix[a][x], "style": _heat_style(matrix[a][x], top)} for x in "XYZ"]}
        for a in "ABC"
    ]
    by_class = frame.groupby("abc_class")["consumption_value"].sum().reindex(list("ABC"), fill_value=0.0)
    total = float(by_class.sum()) or 1.0
    share = bar_chart(
        [f"Class {c}" for c in "ABC"],
        [float(by_class[c]) / total * 100 for c in "ABC"],
        "Consumption value share by ABC class",
        [PALETTE[c] for c in "ABC"],
        "%",
    )
    best = frame.sort_values(["consumption_value", "sku"], ascending=[False, True]).head(10)
    top10 = bar_chart(
        best["sku"].tolist(), [float(v) for v in best["consumption_value"]], "Top 10 SKUs by consumption value"
    )
    plan = result.reorder_plan()
    cfg = result.config
    return {
        "as_of": s["as_of"],
        "subtitle": f"Lookback {cfg.lookback_days} days, service level {cfg.service_level:g}, holding cost rate {cfg.holding_cost_rate:g}",
        "kpis": [
            ("SKUs analysed", str(s["sku_count"])),
            ("Inventory value", money(s["inventory_value"])),
            ("Dead-stock value", money(s["dead_stock_value"])),
            ("Overstock value", money(s["overstock_value"])),
            ("Capital needed", money(s["capital_needed"])),
        ],
        "status_counts": s["status_counts"],
        "heat": heat,
        "share_chart": share,
        "top_chart": top10,
        "headers": [h for _, h in TABLE_COLUMNS],
        "status_index": [c for c, _ in TABLE_COLUMNS].index("status"),
        "urgent": _rows(plan.head(15)),
        "plan": _rows(plan),
        "warnings": result.warnings,
    }


def render(result: AnalysisResult) -> str:
    """Render the report as one HTML document with inline CSS and SVG.

    Args:
        result: The analysis result.

    Returns:
        HTML text with no external requests and no JavaScript.
    """
    env = Environment(
        loader=FileSystemLoader(str(Path(__file__).parent / "templates")),
        autoescape=select_autoescape(["html", "j2"]),
    )
    return env.get_template("report.html.j2").render(**_context(result))
