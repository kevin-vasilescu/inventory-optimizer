from datetime import date

import numpy as np
import pytest

from inventory_optimizer.demand import daily_matrix, demand_stats, weekly_cv
from tests.conftest import make_sales

AS_OF = date(2026, 1, 14)


def test_same_day_rows_are_summed_and_gaps_zero_filled() -> None:
    sales = make_sales([("2026-01-10", "A", 7), ("2026-01-14", "A", 7), ("2026-01-14", "A", 7)])
    m = daily_matrix(sales, ["A"], AS_OF, 14)
    assert len(m) == 14
    assert m["A"].sum() == 21
    assert m.loc["2026-01-14", "A"] == 14


def test_mean_and_sample_std() -> None:
    sales = make_sales([("2026-01-10", "A", 7), ("2026-01-14", "A", 14)])
    stats = demand_stats(daily_matrix(sales, ["A"], AS_OF, 14))
    # mean = 21 / 14 = 1.5; sum of squares 49 + 196 = 245; 245 - 14 * 1.5^2 = 213.5; /13 = 16.423
    assert stats.loc["A", "avg_daily_demand"] == pytest.approx(1.5)
    assert stats.loc["A", "demand_std_daily"] == pytest.approx(4.0525, abs=1e-3)


def test_single_day_window_has_zero_std() -> None:
    sales = make_sales([("2026-01-14", "A", 9)])
    stats = demand_stats(daily_matrix(sales, ["A"], AS_OF, 1))
    assert stats.loc["A", "avg_daily_demand"] == 9
    assert stats.loc["A", "demand_std_daily"] == 0


def test_weekly_cv() -> None:
    # weeks: Jan 1-7 = 0, Jan 8-14 = 21 -> mean 10.5, sample std = sqrt(2 * 10.5^2) -> cv = sqrt(2)
    sales = make_sales([("2026-01-10", "A", 7), ("2026-01-14", "A", 14)])
    cv = weekly_cv(daily_matrix(sales, ["A"], AS_OF, 14))
    assert cv["A"] == pytest.approx(2**0.5)


def test_incomplete_leading_bucket_is_dropped() -> None:
    # 10-day window Jan 5-14: only Jan 8-14 is a full week; the Jan 6 sale is dropped
    sales = make_sales([("2026-01-06", "A", 5), ("2026-01-10", "A", 7)])
    cv = weekly_cv(daily_matrix(sales, ["A"], AS_OF, 10))
    assert cv["A"] == 0.0


def test_zero_demand_has_no_cv() -> None:
    sales = make_sales([("2026-01-14", "B", 1)])
    assert np.isnan(weekly_cv(daily_matrix(sales, ["A"], AS_OF, 14))["A"])


def test_window_shorter_than_a_week_has_no_cv() -> None:
    sales = make_sales([("2026-01-14", "A", 1)])
    assert np.isnan(weekly_cv(daily_matrix(sales, ["A"], AS_OF, 3))["A"])
