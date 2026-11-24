from pathlib import Path

from inventory_optimizer import analyze, load_inventory, load_sales
from inventory_optimizer.sample_data import generate, write_sample


def test_deterministic_for_a_seed() -> None:
    a_sales, a_inv = generate(30, 120, 7)
    b_sales, b_inv = generate(30, 120, 7)
    assert a_sales.equals(b_sales) and a_inv.equals(b_inv)
    c_sales, _ = generate(30, 120, 8)
    assert not a_sales.equals(c_sales)


def test_realistic_mix(tmp_path: Path) -> None:
    write_sample(tmp_path, 200, 365, 42)
    result = analyze(load_sales(tmp_path / "sales.csv"), load_inventory(tmp_path / "inventory.csv"))
    frame = result.to_dataframe()
    assert frame["supplier"].nunique() == 8
    assert frame["category"].nunique() >= 5
    counts = result.summary()["status_counts"]
    assert counts["DEAD"] > 0 and counts["CRITICAL"] + counts["REORDER"] > 0 and counts["OK"] > 0
    assert all("ignored" not in w for w in result.warnings)
