import numpy as np
import pandas as pd

from inventory_optimizer.classification import classify_abc, classify_xyz


def test_abc_boundaries_are_inclusive() -> None:
    # total 100; cumulative shares 0.50, 0.80, 0.95, 1.00 -> A, A (exactly 0.80), B (exactly 0.95), C
    values = pd.Series({"a": 50.0, "b": 30.0, "c": 15.0, "d": 5.0})
    assert classify_abc(values).to_dict() == {"a": "A", "b": "A", "c": "B", "d": "C"}


def test_abc_ties_break_by_sku() -> None:
    # c = 80 (share 0.80 -> A); a and b tie at 10, a ranks first: 0.90 -> B, then b: 1.00 -> C
    values = pd.Series({"b": 10.0, "c": 80.0, "a": 10.0})
    assert classify_abc(values).to_dict() == {"b": "C", "c": "A", "a": "B"}


def test_abc_zero_consumption_is_c() -> None:
    assert classify_abc(pd.Series({"x": 0.0, "y": 0.0})).to_dict() == {"x": "C", "y": "C"}
    mixed = classify_abc(pd.Series({"x": 0.0, "y": 10.0}))
    assert mixed.to_dict() == {"x": "C", "y": "C"}  # single positive SKU has cumulative share 1.0


def test_abc_preserves_index_order() -> None:
    values = pd.Series({"z": 1.0, "a": 99.0})
    assert list(classify_abc(values).index) == ["z", "a"]


def test_xyz_thresholds() -> None:
    cv = pd.Series({"a": 0.5, "b": 0.51, "c": 1.0, "d": 1.01, "e": np.nan})
    assert classify_xyz(cv).to_dict() == {"a": "X", "b": "Y", "c": "Y", "d": "Z", "e": "Z"}
