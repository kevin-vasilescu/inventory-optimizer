"""Purchase-order drafts, one CSV and Markdown file per supplier."""

from __future__ import annotations

import re
from datetime import date
from pathlib import Path

import pandas as pd

from .report.data import export_frame
from .report.markdown import md_table

_RESERVED = {"con", "prn", "aux", "nul", *(f"com{i}" for i in range(1, 10)), *(f"lpt{i}" for i in range(1, 10))}


def sanitize_filename(name: str) -> str:
    """Turn a supplier name into a safe file-name stem for Windows, macOS and Linux.

    Args:
        name: Arbitrary supplier name, possibly with slashes or spaces.

    Returns:
        A non-empty stem containing only letters, digits, dot, dash and underscore.
    """
    stem = re.sub(r"[^A-Za-z0-9._-]+", "_", name.strip()).strip("._") or "supplier"
    return f"_{stem}" if stem.lower() in _RESERVED else stem


def po_markdown(supplier: str, lines: pd.DataFrame, as_of: date) -> str:
    """Render one purchase-order draft as Markdown.

    Args:
        supplier: Supplier name.
        lines: Order lines for that supplier.
        as_of: Order date.

    Returns:
        Markdown text including the order total.
    """
    total = float(lines["line_total"].sum())
    return (
        f"# Purchase order draft: {supplier}\n\n"
        f"- Date: {as_of.isoformat()}\n- Lines: {len(lines)}\n- Order total: {total:,.2f}\n\n"
        f"{md_table(lines, ['sku', 'description', 'qty', 'unit_cost', 'line_total', 'expected_arrival'])}\n\n"
        f"**Order total: {total:,.2f}**\n"
    )


def write_purchase_orders(
    orders: dict[str, pd.DataFrame], directory: str | Path, as_of: date
) -> list[Path]:
    """Write a CSV and a Markdown file for every supplier.

    Args:
        orders: Output of ``AnalysisResult.purchase_orders()``.
        directory: Destination folder (created if needed).
        as_of: Order date used in file names and headers.

    Returns:
        Paths of all files written.
    """
    out = Path(directory)
    out.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    used: set[str] = set()
    for supplier, lines in orders.items():
        stem = f"PO_{sanitize_filename(supplier)}_{as_of.isoformat()}"
        unique, n = stem, 2
        while unique.lower() in used:
            unique, n = f"{stem}_{n}", n + 1
        used.add(unique.lower())
        csv_path, md_path = out / f"{unique}.csv", out / f"{unique}.md"
        total = float(lines["line_total"].sum())
        total_row = pd.DataFrame([{"sku": "TOTAL", "line_total": total}])
        body = export_frame(pd.concat([lines, total_row], ignore_index=True)).to_csv(index=False)
        csv_path.write_text(body, encoding="utf-8", newline="\n")
        md_path.write_text(po_markdown(supplier, lines, as_of), encoding="utf-8", newline="\n")
        written += [csv_path, md_path]
    return written
