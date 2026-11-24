from __future__ import annotations

from datetime import date
from pathlib import Path

import pandas as pd
import pytest

from inventory_optimizer import Config, analyze


def make_sales(rows: list[tuple[str, str, float]]) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "date": pd.to_datetime([r[0] for r in rows]),
            "sku": [r[1] for r in rows],
            "quantity": [float(r[2]) for r in rows],
        }
    )


def make_inventory(**overrides: object) -> pd.DataFrame:
    base: dict[str, object] = {
        "sku": "A",
        "description": "",
        "category": "Uncategorized",
        "supplier": "Acme",
        "unit_cost": 20.0,
        "on_hand": 30.0,
        "on_order": 15.0,
        "lead_time_days": 7.0,
        "lead_time_std_days": 0.0,
        "moq": 100.0,
        "case_pack": 12.0,
        "order_cost": float("nan"),
    }
    base.update(overrides)
    return pd.DataFrame([base])


# Five days with quantities 12, 8, 12, 8, 10: mean 10, squared deviations 4+4+4+4+0 = 16,
# sample variance 16 / 4 = 4, so sigma_d = 2. This reproduces the worked example.
WORKED_SALES = make_sales(
    [("2026-01-01", "A", 12), ("2026-01-02", "A", 8), ("2026-01-03", "A", 12),
     ("2026-01-04", "A", 8), ("2026-01-05", "A", 10)]
)  # fmt: skip


@pytest.fixture
def worked_result():  # type: ignore[no-untyped-def]
    return analyze(WORKED_SALES, make_inventory(), Config(lookback_days=5))


@pytest.fixture
def fixtures_dir() -> Path:
    return Path(__file__).parent / "fixtures"


AS_OF = date(2026, 1, 5)
