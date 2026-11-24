import sys
from pathlib import Path

import pytest
from typer.testing import CliRunner

from inventory_optimizer.cli import app

runner = CliRunner()


@pytest.fixture(scope="module")
def data(tmp_path_factory: pytest.TempPathFactory) -> Path:
    out = tmp_path_factory.mktemp("sample")
    result = runner.invoke(app, ["sample", "--skus", "40", "--days", "200", "--out", str(out)])
    assert result.exit_code == 0
    return out


def args(data: Path, *extra: str) -> list[str]:
    return ["analyze", str(data / "sales.csv"), str(data / "inventory.csv"), *extra]


def test_version() -> None:
    result = runner.invoke(app, ["--version"])
    assert result.exit_code == 0 and "invopt 0.1.0" in result.output


def test_analyze_prints_summary(data: Path) -> None:
    result = runner.invoke(app, args(data, "--top", "3"))
    assert result.exit_code == 0
    assert "Status counts" in result.output and "Total inventory value" in result.output


@pytest.mark.parametrize("fmt", ["md", "html", "json", "csv", "xlsx"])
def test_analyze_writes_every_format(data: Path, tmp_path: Path, fmt: str) -> None:
    out = tmp_path / f"report.{fmt}"
    result = runner.invoke(app, args(data, "--format", fmt, "--out", str(out)))
    assert result.exit_code == 0, result.output
    assert out.stat().st_size > 0


def test_status_filter(data: Path, tmp_path: Path) -> None:
    out = tmp_path / "r.csv"
    result = runner.invoke(app, args(data, "--status", "dead", "--format", "csv", "--out", str(out)))
    assert result.exit_code == 0
    assert set(line.split(",")[21] for line in out.read_text().splitlines()[1:]) <= {"DEAD"}


def test_xlsx_without_openpyxl(data: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setitem(sys.modules, "openpyxl", None)
    result = runner.invoke(app, args(data, "--format", "xlsx", "--out", str(tmp_path / "r.xlsx")))
    assert result.exit_code == 1
    assert "pip install" in result.output and "Traceback" not in result.output


def test_xlsx_requires_out(data: Path) -> None:
    assert runner.invoke(app, args(data, "--format", "xlsx")).exit_code == 2


@pytest.mark.parametrize(
    "extra", [["--service-level", "1"], ["--service-level", "0.5"], ["--as-of", "yesterday"],
              ["--status", "NOPE"], ["--format", "pdf"], ["--lookback-days", "0"]],
)  # fmt: skip
def test_usage_errors_exit_2(data: Path, extra: list[str]) -> None:
    assert runner.invoke(app, args(data, *extra)).exit_code == 2


def test_data_errors_exit_1(data: Path, tmp_path: Path) -> None:
    bad = tmp_path / "bad.csv"
    bad.write_text("date,sku,quantity\n2026-01-01,A,-1\n")
    result = runner.invoke(app, ["analyze", str(bad), str(data / "inventory.csv")])
    assert result.exit_code == 1
    assert "row 2" in result.output and "Traceback" not in result.output
    missing = runner.invoke(app, ["analyze", str(tmp_path / "x.csv"), str(data / "inventory.csv")])
    assert missing.exit_code == 1


def test_validate(data: Path, tmp_path: Path) -> None:
    ok = runner.invoke(app, ["validate", str(data / "sales.csv"), str(data / "inventory.csv")])
    assert ok.exit_code == 0 and "OK" in ok.output
    bad = tmp_path / "inv.csv"
    bad.write_text("sku,supplier,unit_cost,on_hand,lead_time_days\nA,,1,1,1\n")
    result = runner.invoke(app, ["validate", str(data / "sales.csv"), str(bad)])
    assert result.exit_code == 1 and "row 2: supplier is empty" in result.output


def test_po(data: Path, tmp_path: Path) -> None:
    out = tmp_path / "po"
    result = runner.invoke(app, ["po", str(data / "sales.csv"), str(data / "inventory.csv"), "--out", str(out)])
    assert result.exit_code == 0
    assert list(out.glob("PO_*.csv")) and list(out.glob("PO_*.md"))


def test_po_unknown_supplier(data: Path, tmp_path: Path) -> None:
    result = runner.invoke(
        app, ["po", str(data / "sales.csv"), str(data / "inventory.csv"), "--out", str(tmp_path), "--supplier", "Nobody"]
    )
    assert result.exit_code == 2


def test_po_single_supplier(data: Path, tmp_path: Path) -> None:
    result = runner.invoke(
        app,
        ["po", str(data / "sales.csv"), str(data / "inventory.csv"), "--out", str(tmp_path), "--supplier", "Harbor Goods"],
    )
    assert result.exit_code == 0
    assert all("Harbor_Goods" in p.name for p in tmp_path.glob("PO_*"))


def test_nothing_to_order(tmp_path: Path) -> None:
    (tmp_path / "s.csv").write_text("date,sku,quantity\n2026-01-01,A,1\n")
    (tmp_path / "i.csv").write_text("sku,supplier,unit_cost,on_hand,lead_time_days\nA,X,1,1000,1\n")
    result = runner.invoke(app, ["po", str(tmp_path / "s.csv"), str(tmp_path / "i.csv"), "--out", str(tmp_path / "o")])
    assert result.exit_code == 0 and "Nothing to order" in result.output


def test_no_args_shows_help() -> None:
    result = runner.invoke(app, [])
    assert "Usage" in result.output
