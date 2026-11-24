"""The analysis pipeline."""

from __future__ import annotations

from datetime import date
from statistics import NormalDist

import numpy as np
import pandas as pd

from . import policy
from .classification import classify_abc, classify_xyz
from .config import Config
from .demand import daily_matrix, demand_stats, weekly_cv, window_start
from .models import AnalysisResult

MIN_HISTORY_DAYS = 28


def _preview(items: list[str], limit: int = 10) -> str:
    shown = ", ".join(items[:limit])
    return shown + (f" (and {len(items) - limit} more)" if len(items) > limit else "")


def _divide(num: pd.Series, den: pd.Series) -> pd.Series:
    """Element-wise division returning NaN where the denominator is not positive."""
    return num / den.where(den > 0)


def analyze(
    sales: pd.DataFrame, inventory: pd.DataFrame, config: Config = Config()
) -> AnalysisResult:
    """Classify SKUs and compute reorder recommendations.

    Args:
        sales: Output of :func:`load_sales`.
        inventory: Output of :func:`load_inventory`.
        config: Analysis settings.

    Returns:
        The :class:`AnalysisResult`.
    """
    latest = sales["date"].max().date()
    as_of: date = config.as_of or latest
    cfg = Config(**{**config.__dict__, "as_of": as_of})
    warnings: list[str] = []

    known = set(inventory["sku"])
    unknown = sorted(set(sales["sku"]) - known)
    if unknown:
        warnings.append(f"{len(unknown)} SKU(s) in sales but not in inventory were ignored: {_preview(unknown)}")
    if as_of < latest:
        warnings.append(f"as_of {as_of} is earlier than the latest sale {latest}; later sales were ignored")
    first = max(sales["date"].min().date(), window_start(as_of, cfg.lookback_days))
    history = (as_of - first).days + 1
    if history < MIN_HISTORY_DAYS:
        warnings.append(f"only {max(history, 0)} day(s) of history in the lookback window (fewer than {MIN_HISTORY_DAYS})")

    skus = inventory["sku"].tolist()
    upto = sales[(sales["date"] <= pd.Timestamp(as_of)) & sales["sku"].isin(known)]
    no_sales = sorted(known - set(upto["sku"]))
    if no_sales:
        warnings.append(f"{len(no_sales)} SKU(s) in inventory have no sales and get zero demand: {_preview(no_sales)}")

    matrix = daily_matrix(upto, skus, as_of, cfg.lookback_days)
    df = inventory.set_index("sku", drop=False).copy()
    df.index.name = None
    stats = demand_stats(matrix)
    d = stats["avg_daily_demand"].reindex(df.index)
    sigma = stats["demand_std_daily"].reindex(df.index)
    lt, sigma_lt, unit_cost = df["lead_time_days"], df["lead_time_std_days"], df["unit_cost"]

    df["avg_daily_demand"] = d
    df["demand_std_daily"] = sigma
    df["annual_demand"] = d * 365
    df["consumption_value"] = df["annual_demand"] * unit_cost
    df["weekly_cv"] = weekly_cv(matrix).reindex(df.index)
    df["abc_class"] = classify_abc(df["consumption_value"], cfg.abc_thresholds)
    df["xyz_class"] = classify_xyz(df["weekly_cv"], cfg.xyz_thresholds)

    z = NormalDist().inv_cdf(cfg.service_level)
    exact = policy.safety_stock_unrounded(z, lt, sigma, d, sigma_lt)
    df["safety_stock"] = np.ceil(exact.round(9))
    df["reorder_point"] = policy.reorder_point(d, lt, exact)
    order_cost = df["order_cost"].fillna(cfg.default_order_cost)
    holding = cfg.holding_cost_rate * unit_cost
    df["eoq"] = policy.eoq(df["annual_demand"], order_cost, holding)
    df["inventory_position"] = df["on_hand"] + df["on_order"]
    df["days_of_cover"] = _divide(df["on_hand"], d)
    df["order_up_to"] = df["reorder_point"] + df["eoq"]

    raw_need = df["order_up_to"] - df["inventory_position"]
    qty = policy.round_order_qty(raw_need, df["moq"], df["case_pack"])
    needs_order = (df["annual_demand"] > 0) & (df["inventory_position"] <= df["reorder_point"])
    df["recommended_order_qty"] = qty.where(needs_order, 0.0)
    df["order_value"] = df["recommended_order_qty"] * unit_cost
    arrival = pd.Timestamp(as_of) + pd.to_timedelta(np.ceil(lt), unit="D")
    df["expected_arrival"] = arrival.dt.date

    last_sale = upto.groupby("sku")["date"].max().reindex(df.index)
    df["last_sale_date"] = last_sale.dt.date.astype(object).where(last_sale.notna(), None)
    df["inventory_value"] = df["on_hand"] * unit_cost
    df["turnover"] = _divide(df["annual_demand"] * unit_cost, df["inventory_value"])
    df["excess_units"] = (df["on_hand"] - df["order_up_to"]).clip(lower=0)
    df["excess_value"] = df["excess_units"] * unit_cost

    idle_days = (pd.Timestamp(as_of) - last_sale).dt.days
    dead = (df["on_hand"] > 0) & (last_sale.isna() | (idle_days >= cfg.dead_stock_days))
    at_or_below = (df["annual_demand"] > 0) & (df["inventory_position"] <= df["reorder_point"])
    critical = at_or_below & (df["days_of_cover"] < lt)
    overstock = df["days_of_cover"] > cfg.overstock_days
    df["status"] = np.select([dead, critical, at_or_below, overstock], ["DEAD", "CRITICAL", "REORDER", "OVERSTOCK"], "OK")

    columns = [
        "sku", "description", "category", "supplier", "abc_class", "xyz_class",
        "avg_daily_demand", "demand_std_daily", "annual_demand", "consumption_value",
        "weekly_cv", "unit_cost", "on_hand", "on_order", "inventory_position",
        "lead_time_days", "safety_stock", "reorder_point", "eoq", "order_up_to",
        "days_of_cover", "status", "recommended_order_qty", "order_value",
        "expected_arrival", "last_sale_date", "inventory_value", "turnover",
        "excess_units", "excess_value",
    ]  # fmt: skip
    return AnalysisResult(df[columns].reset_index(drop=True), cfg, as_of, warnings)
