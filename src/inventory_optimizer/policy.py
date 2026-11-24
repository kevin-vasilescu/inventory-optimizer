"""Pure inventory-policy formulas. Every function accepts floats or pandas Series."""

from __future__ import annotations

from typing import TypeVar, cast

import numpy as np
import pandas as pd

Num = TypeVar("Num", float, pd.Series)


def _ceil(x: Num) -> Num:
    """Round up, ignoring floating-point noise below 1e-9."""
    return cast(Num, np.ceil(np.round(x, 9)))


def safety_stock_unrounded(
    z: float, lead_time: Num, sigma_d: Num, demand: Num, sigma_lead_time: Num
) -> Num:
    """Safety stock before rounding.

    ``z * sqrt(LT * sigma_d^2 + d^2 * sigma_LT^2)``

    Args:
        z: Standard-normal quantile for the service level.
        lead_time: Lead time in days.
        sigma_d: Standard deviation of daily demand.
        demand: Average daily demand.
        sigma_lead_time: Standard deviation of lead time in days.

    Returns:
        Unrounded safety stock in units.
    """
    return cast(Num, z * np.sqrt(lead_time * sigma_d**2 + demand**2 * sigma_lead_time**2))


def safety_stock(
    z: float, lead_time: Num, sigma_d: Num, demand: Num, sigma_lead_time: Num
) -> Num:
    """Safety stock rounded up to whole units.

    Args:
        z: Standard-normal quantile for the service level.
        lead_time: Lead time in days.
        sigma_d: Standard deviation of daily demand.
        demand: Average daily demand.
        sigma_lead_time: Standard deviation of lead time in days.

    Returns:
        Safety stock in units.
    """
    return _ceil(safety_stock_unrounded(z, lead_time, sigma_d, demand, sigma_lead_time))


def reorder_point(demand: Num, lead_time: Num, safety_stock_exact: Num) -> Num:
    """Reorder point ``ceil(d * LT + unrounded safety stock)``.

    Args:
        demand: Average daily demand.
        lead_time: Lead time in days.
        safety_stock_exact: Unrounded safety stock.

    Returns:
        Reorder point in units.
    """
    return _ceil(demand * lead_time + safety_stock_exact)


def eoq(annual_demand: Num, order_cost: Num, holding_cost: Num) -> Num:
    """Economic order quantity ``ceil(sqrt(2 * D * S / H))``; 0 when demand is 0.

    Args:
        annual_demand: Units per year.
        order_cost: Fixed cost per order.
        holding_cost: Holding cost per unit per year (must be positive).

    Returns:
        Order quantity in units.
    """
    return _ceil(cast(Num, np.sqrt(2 * annual_demand * order_cost / holding_cost)))


def round_order_qty(raw: Num, moq: Num, case_pack: Num) -> Num:
    """Apply the minimum order quantity, then round up to a case-pack multiple.

    Args:
        raw: Needed quantity before constraints.
        moq: Minimum order quantity.
        case_pack: Orders must be a multiple of this.

    Returns:
        Orderable quantity.
    """
    return cast(Num, _ceil(cast(Num, np.maximum(raw, moq) / case_pack)) * case_pack)
