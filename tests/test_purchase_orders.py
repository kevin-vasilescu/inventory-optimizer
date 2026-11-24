from datetime import date
from pathlib import Path

import pandas as pd

from inventory_optimizer.purchase_orders import po_markdown, sanitize_filename, write_purchase_orders


def lines() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "sku": ["A", "B"],
            "description": ["Alpha", ""],
            "qty": [10.0, 5.0],
            "unit_cost": [2.5, 4.0],
            "line_total": [25.0, 20.0],
            "expected_arrival": [date(2026, 1, 12)] * 2,
        }
    )


def test_sanitize() -> None:
    assert sanitize_filename("Acme/East Ltd.") == "Acme_East_Ltd"
    assert sanitize_filename("a\\b:c*d?") == "a_b_c_d"
    assert sanitize_filename("CON") == "_CON"
    assert sanitize_filename("///") == "supplier"


def test_write_files_and_totals(tmp_path: Path) -> None:
    paths = write_purchase_orders({"Delta/Gamma Imports": lines()}, tmp_path / "po", date(2026, 1, 5))
    assert sorted(p.name for p in paths) == [
        "PO_Delta_Gamma_Imports_2026-01-05.csv",
        "PO_Delta_Gamma_Imports_2026-01-05.md",
    ]
    csv_text = paths[0].read_text(encoding="utf-8")
    assert csv_text.splitlines()[0] == "sku,description,qty,unit_cost,line_total,expected_arrival"
    assert csv_text.splitlines()[-1].startswith("TOTAL,") and ",45," in csv_text.splitlines()[-1]
    assert "Order total: 45.00" in paths[1].read_text(encoding="utf-8")


def test_colliding_names_stay_unique(tmp_path: Path) -> None:
    paths = write_purchase_orders({"A/B": lines(), "A B": lines()}, tmp_path, date(2026, 1, 5))
    assert len({p.name for p in paths}) == 4


def test_markdown_lists_lines() -> None:
    text = po_markdown("Acme", lines(), date(2026, 1, 5))
    assert "| A | Alpha | 10 | 2.50 | 25 | 2026-01-12 |" in text
