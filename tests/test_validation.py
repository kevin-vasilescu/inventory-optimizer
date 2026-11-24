from pathlib import Path

import pytest

from inventory_optimizer import load_inventory, load_sales
from inventory_optimizer.validation import DataError

GOOD_INV = "sku,supplier,unit_cost,on_hand,lead_time_days\nA,Acme,2.5,10,7\n"


def write(tmp_path: Path, name: str, text: str) -> Path:
    path = tmp_path / name
    path.write_text(text, encoding="utf-8")
    return path


def problems(loader, path: Path) -> list[str]:  # type: ignore[no-untyped-def]
    with pytest.raises(DataError) as info:
        loader(path)
    return info.value.problems


def test_valid_sales_and_defaults(tmp_path: Path) -> None:
    sales = load_sales(write(tmp_path, "s.csv", "date,sku,quantity\n2026-01-01,A,3\n"))
    assert sales.loc[0, "quantity"] == 3
    inv = load_inventory(write(tmp_path, "i.csv", GOOD_INV))
    row = inv.iloc[0]
    assert (row["category"], row["description"], row["on_order"], row["moq"], row["case_pack"]) == (
        "Uncategorized", "", 0, 1, 1)  # fmt: skip
    assert row["lead_time_std_days"] == 0


def test_bom_and_header_case(tmp_path: Path) -> None:
    sales = load_sales(write(tmp_path, "s.csv", "\ufeffDate, SKU ,Quantity\n2026-01-01,A,3\n"))
    assert list(sales.columns) == ["date", "sku", "quantity"]


def test_missing_file_and_empty_file(tmp_path: Path) -> None:
    assert "not found" in problems(load_sales, tmp_path / "nope.csv")[0]
    assert "empty" in problems(load_sales, write(tmp_path, "e.csv", ""))[0]
    assert "no data rows" in problems(load_sales, write(tmp_path, "h.csv", "date,sku,quantity\n"))[0]


def test_missing_columns(tmp_path: Path) -> None:
    msgs = problems(load_sales, write(tmp_path, "s.csv", "date,sku\n2026-01-01,A\n"))
    assert "missing required column(s): quantity" in msgs[0]


def test_sales_row_errors_have_row_numbers(tmp_path: Path) -> None:
    text = "date,sku,quantity\n2026-01-01,A,1\n2026-13-45,A,1\n2026-01-03,,1\n2026-01-04,A,-2\n2026-01-05,A,abc\n2026-01-06,A,\n"
    msgs = problems(load_sales, write(tmp_path, "s.csv", text))
    joined = "\n".join(msgs)
    assert "row 3: date '2026-13-45'" in joined
    assert "row 4: sku is empty" in joined
    assert "row 5: quantity '-2'" in joined
    assert "row 6: quantity 'abc' is not a number" in joined
    assert "row 7: quantity is required" in joined
    assert "row 2" not in joined


def test_inventory_row_errors(tmp_path: Path) -> None:
    text = (
        "sku,supplier,unit_cost,on_hand,on_order,lead_time_days\n"
        "A,Acme,2,1,0,5\n"
        "A,Acme,2,1,0,5\n"
        ",Acme,2,1,0,5\n"
        "B,,2,1,0,5\n"
        "C,Acme,0,1,0,5\n"
        "D,Acme,2,-1,0,5\n"
        "E,Acme,2,1,-3,5\n"
        "F,Acme,2,1,0,0\n"
    )
    joined = "\n".join(problems(load_inventory, write(tmp_path, "i.csv", text)))
    for expected in [
        "row 3: duplicate sku 'A'", "row 4: sku is empty", "row 5: supplier is empty",
        "row 6: unit_cost '0'", "row 7: on_hand '-1'", "row 8: on_order '-3'", "row 9: lead_time_days '0'",
    ]:  # fmt: skip
        assert expected in joined


def test_optional_numeric_columns_validated(tmp_path: Path) -> None:
    text = GOOD_INV.replace("lead_time_days", "lead_time_days,moq").replace("7\n", "7,0\n")
    assert "moq" in problems(load_inventory, write(tmp_path, "i.csv", text))[0]
