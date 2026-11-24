"""Excel workbook export (optional ``excel`` extra)."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import pandas as pd

from .data import export_frame

if TYPE_CHECKING:
    from ..models import AnalysisResult

MAX_WIDTH = 48
INSTALL_HINT = 'Excel output needs openpyxl. Install it with: pip install "inventory-optimizer[excel]"'


class MissingExtraError(RuntimeError):
    """Raised when the optional openpyxl dependency is not installed."""


def _summary_rows(result: AnalysisResult) -> pd.DataFrame:
    s = result.summary()
    rows: list[tuple[str, object]] = [
        ("As of", s["as_of"]),
        ("SKUs analysed", s["sku_count"]),
        ("Inventory value", round(s["inventory_value"], 2)),
        ("Dead-stock value", round(s["dead_stock_value"], 2)),
        ("Overstock value", round(s["overstock_value"], 2)),
        ("Capital needed", round(s["capital_needed"], 2)),
        *((f"Status {k}", v) for k, v in s["status_counts"].items()),
        *((f"Warning {i + 1}", w) for i, w in enumerate(result.warnings)),
    ]
    return pd.DataFrame(rows, columns=["Metric", "Value"])


def write(result: AnalysisResult, path: Path) -> None:
    """Write the Summary, All SKUs and Reorder Plan sheets.

    Args:
        result: The analysis result.
        path: Destination file.

    Raises:
        MissingExtraError: If openpyxl is not installed.
    """
    try:
        from openpyxl import styles
    except ImportError as exc:
        raise MissingExtraError(INSTALL_HINT) from exc

    sheets = {
        "Summary": _summary_rows(result),
        "All SKUs": export_frame(result.frame),
        "Reorder Plan": export_frame(result.reorder_plan()),
    }
    with pd.ExcelWriter(path, engine="openpyxl") as writer:
        for name, frame in sheets.items():
            frame.to_excel(writer, sheet_name=name, index=False)
            sheet = writer.sheets[name]
            sheet.freeze_panes = "A2"
            for cell in sheet[1]:
                cell.font = styles.Font(bold=True, color="FFFFFF")
                cell.fill = styles.PatternFill("solid", fgColor="0F172A")
                cell.alignment = styles.Alignment(horizontal="center")
            for column in sheet.columns:
                longest = max(len(str(c.value)) if c.value is not None else 0 for c in column)
                sheet.column_dimensions[column[0].column_letter].width = min(longest + 2, MAX_WIDTH)
