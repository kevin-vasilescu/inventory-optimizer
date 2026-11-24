"""Result container for an analysis run."""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from datetime import date
from pathlib import Path
from typing import Any

import pandas as pd

from .config import Config

STATUSES = ("DEAD", "CRITICAL", "REORDER", "OVERSTOCK", "OK")
_URGENCY = {"CRITICAL": 0, "REORDER": 1}

PLAN_COLUMNS = [
    "sku",
    "description",
    "supplier",
    "status",
    "abc_class",
    "xyz_class",
    "on_hand",
    "on_order",
    "inventory_position",
    "reorder_point",
    "days_of_cover",
    "recommended_order_qty",
    "unit_cost",
    "order_value",
    "expected_arrival",
]

PO_COLUMNS = ["sku", "description", "qty", "unit_cost", "line_total", "expected_arrival"]


@dataclass(frozen=True)
class AnalysisResult:
    """Outcome of :func:`inventory_optimizer.analyze`.

    Attributes:
        frame: One row per SKU. Undefined values (for example days of cover with zero
            demand) are NaN or None here and become null/empty in every export.
        config: The configuration used (with ``as_of`` resolved).
        as_of: The reference date.
        warnings: Non-fatal data warnings.
    """

    frame: pd.DataFrame
    config: Config
    as_of: date
    warnings: list[str] = field(default_factory=list)

    def to_dataframe(self) -> pd.DataFrame:
        """Return the full per-SKU table.

        Returns:
            A copy of the result frame.
        """
        return self.frame.copy()

    def filter_status(self, statuses: list[str]) -> AnalysisResult:
        """Keep only SKUs with the given statuses.

        Args:
            statuses: Status names such as ``["CRITICAL", "REORDER"]``.

        Returns:
            A new result; its summary reflects only the kept SKUs.
        """
        keep = self.frame["status"].isin(statuses)
        return replace(self, frame=self.frame[keep].reset_index(drop=True))

    def reorder_plan(self) -> pd.DataFrame:
        """SKUs with a recommended order, most urgent first.

        Returns:
            Rows with a positive order quantity, ordered by status urgency, days of
            cover and SKU.
        """
        plan = self.frame[self.frame["recommended_order_qty"] > 0].copy()
        plan["_u"] = plan["status"].map(_URGENCY).fillna(9)
        plan = plan.sort_values(["_u", "days_of_cover", "sku"], na_position="last")
        return plan[PLAN_COLUMNS].reset_index(drop=True)

    def purchase_orders(self) -> dict[str, pd.DataFrame]:
        """Purchase-order lines grouped by supplier.

        Returns:
            Mapping of supplier name to lines (sku, description, qty, unit_cost,
            line_total, expected_arrival).
        """
        plan = self.reorder_plan()
        lines = plan.assign(qty=plan["recommended_order_qty"], line_total=plan["order_value"])
        lines = lines.assign(supplier=plan["supplier"])
        orders: dict[str, pd.DataFrame] = {}
        for supplier, group in lines.groupby("supplier", sort=True):
            orders[str(supplier)] = group[PO_COLUMNS].reset_index(drop=True)
        return orders

    def summary(self) -> dict[str, Any]:
        """Headline numbers.

        Returns:
            Dict with sku_count, inventory_value, dead_stock_value, overstock_value
            (excess value of OVERSTOCK SKUs), capital_needed, status_counts and the
            ABC x XYZ matrix of SKU counts.
        """
        f = self.frame
        counts = f["status"].value_counts()
        matrix = pd.crosstab(f["abc_class"], f["xyz_class"]).reindex(
            index=list("ABC"), columns=list("XYZ"), fill_value=0
        )
        return {
            "as_of": self.as_of.isoformat(),
            "sku_count": len(f),
            "inventory_value": float(f["inventory_value"].sum()),
            "dead_stock_value": float(f.loc[f["status"] == "DEAD", "inventory_value"].sum()),
            "overstock_value": float(f.loc[f["status"] == "OVERSTOCK", "excess_value"].sum()),
            "capital_needed": float(f["order_value"].sum()),
            "status_counts": {s: int(counts.get(s, 0)) for s in STATUSES},
            "abc_xyz": {a: {x: int(matrix.loc[a, x]) for x in "XYZ"} for a in "ABC"},
        }

    def to_json(self) -> str:
        """Serialise config, summary, warnings and all SKUs as JSON.

        Returns:
            A JSON string with a stable schema (see docs/usage.md).
        """
        from .report.data import to_json

        return to_json(self)

    def to_csv(self) -> str:
        """Serialise the full per-SKU table as CSV.

        Returns:
            CSV text with a header row; undefined values are empty.
        """
        from .report.data import export_frame

        return export_frame(self.frame).to_csv(index=False)

    def to_markdown(self) -> str:
        """Render the Markdown report.

        Returns:
            Markdown text.
        """
        from .report.markdown import render

        return render(self)

    def to_html(self) -> str:
        """Render the self-contained HTML report.

        Returns:
            A complete HTML document.
        """
        from .report.html import render

        return render(self)

    def to_excel(self, path: str | Path) -> None:
        """Write the Excel workbook (needs the ``excel`` extra).

        Args:
            path: Destination ``.xlsx`` path.

        Raises:
            MissingExtraError: If openpyxl is not installed.
        """
        from .report.excel import write

        write(self, Path(path))
