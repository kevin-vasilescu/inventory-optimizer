import pytest

from inventory_optimizer import Config
from inventory_optimizer.config import ConfigError
from inventory_optimizer.policy import eoq, reorder_point, round_order_qty, safety_stock, safety_stock_unrounded

Z95 = 1.644854


def test_worked_example_safety_stock() -> None:
    # 1.644854 * sqrt(7 * 2^2 + 10^2 * 0) = 1.644854 * 5.291503 = 8.7036 -> 9
    assert safety_stock_unrounded(Z95, 7, 2, 10, 0) == pytest.approx(8.7036, abs=1e-3)
    assert safety_stock(Z95, 7, 2, 10, 0) == 9


def test_worked_example_reorder_point() -> None:
    # ceil(10 * 7 + 8.7036) = ceil(78.7036) = 79
    assert reorder_point(10, 7, 8.7036) == 79


def test_worked_example_eoq() -> None:
    # H = 0.25 * 20 = 5; sqrt(2 * 3650 * 50 / 5) = sqrt(73000) = 270.185 -> 271
    assert eoq(3650, 50, 5) == 271


def test_worked_example_order_rounding() -> None:
    # raw = 350 - 45 = 305, moq 100 does not bind, ceil(305 / 12) = 26 cases -> 312
    assert round_order_qty(305, 100, 12) == 312


def test_lead_time_std_adds_variance() -> None:
    # sqrt(7 * 4 + 100 * 1) = sqrt(128) = 11.3137; 1.644854 * 11.3137 = 18.609 -> 19
    assert safety_stock(Z95, 7, 2, 10, 1) == 19
    # reorder point: ceil(70 + 18.609) = 89
    assert reorder_point(10, 7, safety_stock_unrounded(Z95, 7, 2, 10, 1)) == 89


def test_moq_larger_than_need() -> None:
    # raw 20 < moq 100 -> 100 -> ceil(100 / 12) = 9 cases = 108
    assert round_order_qty(20, 100, 12) == 108


def test_exact_case_multiple_not_rounded_up() -> None:
    assert round_order_qty(24, 1, 12) == 24


def test_eoq_zero_demand() -> None:
    assert eoq(0, 50, 5) == 0


def test_floating_noise_does_not_add_a_unit() -> None:
    assert reorder_point(0.1 * 3, 10, 0.0) == 3


@pytest.mark.parametrize("level", [0.5, 1.0, 0.2, 1.5])
def test_service_level_bounds_rejected(level: float) -> None:
    with pytest.raises(ConfigError):
        Config(service_level=level)


@pytest.mark.parametrize(
    "kwargs",
    [{"lookback_days": 0}, {"holding_cost_rate": 0}, {"default_order_cost": -1},
     {"abc_thresholds": (0.9, 0.8)}, {"xyz_thresholds": (1.0, 0.5)}, {"dead_stock_days": 0}],
)  # fmt: skip
def test_invalid_config_rejected(kwargs: dict[str, object]) -> None:
    with pytest.raises(ConfigError):
        Config(**kwargs)  # type: ignore[arg-type]
