"""Run configuration."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date


class ConfigError(ValueError):
    """Raised when a configuration value is out of range."""


@dataclass(frozen=True)
class Config:
    """Analysis settings.

    Attributes:
        as_of: Reference date. Defaults to the latest date in the sales file.
        lookback_days: Length of the demand window ending at ``as_of`` (inclusive).
        service_level: Target cycle service level, strictly between 0.5 and 1.
        holding_cost_rate: Annual holding cost as a fraction of unit cost.
        default_order_cost: Fixed cost per order when a SKU has no ``order_cost``.
        abc_thresholds: Cumulative consumption-value cutoffs for classes A and B.
        xyz_thresholds: Weekly coefficient-of-variation cutoffs for classes X and Y.
        dead_stock_days: Days without a sale after which stock on hand is dead.
        overstock_days: Days of cover above which a SKU is overstocked.
    """

    as_of: date | None = None
    lookback_days: int = 90
    service_level: float = 0.95
    holding_cost_rate: float = 0.25
    default_order_cost: float = 50.0
    abc_thresholds: tuple[float, float] = (0.80, 0.95)
    xyz_thresholds: tuple[float, float] = (0.5, 1.0)
    dead_stock_days: int = 180
    overstock_days: int = 120

    def __post_init__(self) -> None:
        if self.lookback_days < 1:
            raise ConfigError("lookback_days must be at least 1")
        if not 0.5 < self.service_level < 1:
            raise ConfigError("service_level must be strictly between 0.5 and 1")
        if self.holding_cost_rate <= 0:
            raise ConfigError("holding_cost_rate must be greater than 0")
        if self.default_order_cost < 0:
            raise ConfigError("default_order_cost must not be negative")
        a, b = self.abc_thresholds
        if not 0 < a <= b <= 1:
            raise ConfigError("abc_thresholds must satisfy 0 < A <= B <= 1")
        x, y = self.xyz_thresholds
        if not 0 <= x <= y:
            raise ConfigError("xyz_thresholds must satisfy 0 <= X <= Y")
        if self.dead_stock_days < 1 or self.overstock_days < 1:
            raise ConfigError("dead_stock_days and overstock_days must be at least 1")
