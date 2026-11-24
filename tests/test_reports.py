import json
import sys
from pathlib import Path

import pytest

from inventory_optimizer import Config, analyze
from inventory_optimizer.report.excel import MissingExtraError
from inventory_optimizer.sample_data import generate
from tests.conftest import WORKED_SALES, make_inventory


@pytest.fixture(scope="module")
def big():  # type: ignore[no-untyped-def]
    sales, inv = generate(60, 200, 1)
    sales["date"] = sales["date"].astype("datetime64[ns]")
    return analyze(sales, inv)


def test_markdown_sections(worked_result) -> None:  # type: ignore[no-untyped-def]
    text = worked_result.to_markdown()
    for heading in ["# Inventory optimization report", "## Key figures", "## ABC x XYZ matrix",
                    "## Most urgent SKUs", "## Full reorder plan", "## Warnings"]:  # fmt: skip
        assert heading in text
    assert "| Capital needed for recommended orders | 6,240.00 |" in text
    assert "| CRITICAL |" in text


def test_html_is_self_contained(big) -> None:  # type: ignore[no-untyped-def]
    html = big.to_html()
    assert html.startswith("<!DOCTYPE html>")
    for forbidden in ["<script", "<link", "src=", "href=", "@import", "url("]:
        assert forbidden not in html
    assert html.count("<svg") == 2
    assert "badge CRITICAL" in html and "rgba(37,99,235" in html


def test_html_escapes_text() -> None:
    inv = make_inventory(description="<b>x</b>", supplier="A&B")
    html = analyze(WORKED_SALES, inv, Config(lookback_days=5)).to_html()
    assert "A&amp;B" in html


def test_json_schema_and_no_nan(worked_result, big) -> None:  # type: ignore[no-untyped-def]
    def reject(token: str) -> None:
        raise AssertionError(token)

    for result in (worked_result, big):
        data = json.loads(result.to_json(), parse_constant=reject)
        assert list(data) == ["as_of", "config", "summary", "warnings", "skus"]
    first = json.loads(worked_result.to_json())["skus"][0]
    assert first["reorder_point"] == 79 and first["expected_arrival"] == "2026-01-12"
    assert any(row["days_of_cover"] is None for row in json.loads(big.to_json())["skus"])


def test_csv_has_no_nan_or_inf(big) -> None:  # type: ignore[no-untyped-def]
    body = big.to_csv().lower().split("\n", 1)[1]
    assert "nan" not in body and "inf" not in body


def test_excel_workbook(worked_result, tmp_path: Path) -> None:  # type: ignore[no-untyped-def]
    from openpyxl import load_workbook

    path = tmp_path / "r.xlsx"
    worked_result.to_excel(path)
    wb = load_workbook(path)
    assert wb.sheetnames == ["Summary", "All SKUs", "Reorder Plan"]
    assert wb["All SKUs"].freeze_panes == "A2"
    assert wb["All SKUs"]["A1"].font.bold
    assert wb["All SKUs"].column_dimensions["A"].width >= 3


def test_excel_missing_extra(worked_result, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.setitem(sys.modules, "openpyxl", None)
    with pytest.raises(MissingExtraError):
        worked_result.to_excel(tmp_path / "r.xlsx")
