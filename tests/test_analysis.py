from datetime import date

import numpy as np
import pandas as pd
import pytest

from inventory_optimizer import Config, analyze
from tests.conftest import WORKED_SALES, make_inventory, make_sales


def test_worked_example(worked_result) -> None:  # type: ignore[no-untyped-def]
    row = worked_result.to_dataframe().iloc[0]
    assert row["avg_daily_demand"] == pytest.approx(10)
    assert row["demand_std_daily"] == pytest.approx(2)
    assert row["annual_demand"] == pytest.approx(3650)
    assert row["safety_stock"] == 9
    assert row["reorder_point"] == 79
    assert row["eoq"] == 271
    assert row["inventory_position"] == 45
    assert row["order_up_to"] == 350
    assert row["recommended_order_qty"] == 312
    assert row["order_value"] == 6240  # 312 * 20
    assert row["days_of_cover"] == 3  # 30 / 10
    assert row["status"] == "CRITICAL"
    assert row["expected_arrival"] == date(2026, 1, 12)  # as_of Jan 5 + 7 days
    assert row["inventory_value"] == 600  # 30 * 20
    assert row["turnover"] == pytest.approx(3650 * 20 / 600)


def test_on_order_covering_need_means_no_reorder() -> None:
    inv = make_inventory(on_order=70.0)  # position 100 > reorder point 79
    row = analyze(WORKED_SALES, inv, Config(lookback_days=5)).to_dataframe().iloc[0]
    assert row["recommended_order_qty"] == 0
    assert row["status"] == "OK"


def test_zero_demand_sku_is_safe() -> None:
    sales = make_sales([("2026-01-05", "B", 1)])
    inv = make_inventory(on_hand=0.0, on_order=0.0)
    result = analyze(sales, inv, Config(lookback_days=5))
    row = result.to_dataframe().iloc[0]
    assert row["recommended_order_qty"] == 0
    assert row["eoq"] == 0
    assert np.isnan(row["days_of_cover"])
    assert np.isnan(row["turnover"])
    assert row["abc_class"] == "C"
    assert row["status"] == "OK"
    assert any("no sales" in w for w in result.warnings)


def test_zero_demand_with_stock_is_dead() -> None:
    sales = make_sales([("2026-01-05", "B", 1)])
    row = analyze(sales, make_inventory(), Config(lookback_days=5)).to_dataframe().iloc[0]
    assert row["status"] == "DEAD"


def test_all_skus_dead() -> None:
    sales = make_sales([("2026-01-01", "A", 5), ("2026-01-01", "B", 5)])
    one = make_inventory()
    inv = pd.concat([one, one.assign(sku="B")], ignore_index=True)
    result = analyze(sales, inv, Config(as_of=date(2026, 12, 31), lookback_days=30))
    assert set(result.to_dataframe()["status"]) == {"DEAD"}
    assert result.summary()["dead_stock_value"] == 1200  # 2 SKUs * 30 * 20


def test_overstock() -> None:
    # demand 1/day, on hand 500 -> 500 days of cover > 120
    sales = make_sales([(f"2026-01-0{i}", "A", 1) for i in range(1, 6)])
    inv = make_inventory(on_hand=500.0, on_order=0.0, lead_time_days=5.0, moq=1.0, case_pack=1.0)
    result = analyze(sales, inv, Config(lookback_days=5))
    row = result.to_dataframe().iloc[0]
    assert row["status"] == "OVERSTOCK"
    assert row["excess_units"] == 500 - row["order_up_to"]
    assert result.summary()["overstock_value"] == row["excess_value"]


def test_sku_missing_from_inventory_is_ignored_with_warning() -> None:
    sales = make_sales([("2026-01-05", "A", 1), ("2026-01-05", "GHOST", 9)])
    result = analyze(sales, make_inventory(), Config(lookback_days=5))
    assert list(result.to_dataframe()["sku"]) == ["A"]
    assert any("GHOST" in w for w in result.warnings)


def test_as_of_before_latest_sale_ignores_later_sales() -> None:
    cfg = Config(as_of=date(2026, 1, 3), lookback_days=3)
    result = analyze(WORKED_SALES, make_inventory(), cfg)
    # Jan 1-3 quantities 12, 8, 12: mean 32 / 3
    assert result.to_dataframe().iloc[0]["avg_daily_demand"] == pytest.approx(32 / 3)
    assert any("earlier than the latest sale" in w for w in result.warnings)


def test_default_as_of_is_latest_sale(worked_result) -> None:  # type: ignore[no-untyped-def]
    assert worked_result.as_of == date(2026, 1, 5)


def test_short_history_warns(worked_result) -> None:  # type: ignore[no-untyped-def]
    assert any("fewer than 28" in w for w in worked_result.warnings)


def test_summary_and_reorder_plan(worked_result) -> None:  # type: ignore[no-untyped-def]
    s = worked_result.summary()
    assert s["sku_count"] == 1
    assert s["status_counts"]["CRITICAL"] == 1
    assert s["capital_needed"] == 6240
    assert len(worked_result.reorder_plan()) == 1
    assert worked_result.purchase_orders()["Acme"].iloc[0]["qty"] == 312


def test_filter_status(worked_result) -> None:  # type: ignore[no-untyped-def]
    assert len(worked_result.filter_status(["OK"]).to_dataframe()) == 0
    assert len(worked_result.filter_status(["CRITICAL"]).to_dataframe()) == 1


def test_no_infinite_values() -> None:
    sales = make_sales([("2026-01-05", "A", 0)])
    frame = analyze(sales, make_inventory(on_hand=0.0), Config(lookback_days=5)).to_dataframe()
    numeric = frame.select_dtypes("number")
    assert not np.isinf(numeric.to_numpy()).any()
