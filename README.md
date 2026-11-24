# inventory-optimizer

Turn sales history and stock levels into ABC/XYZ classes, safety stock, reorder points, EOQ and supplier purchase orders in one command.

[![CI](https://github.com/kevin-vasilescu/inventory-optimizer/actions/workflows/ci.yml/badge.svg)](https://github.com/kevin-vasilescu/inventory-optimizer/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/github/license/kevin-vasilescu/inventory-optimizer)](LICENSE)
![Python versions](https://img.shields.io/badge/python-3.10%20%7C%203.11%20%7C%203.12%20%7C%203.13-blue)

## Why this exists

Small retailers, e-commerce shops and distributors usually have the data for a good reorder plan: a CSV of sales from the POS or ERP and a CSV of current stock. What they lack is a trustworthy, transparent way to turn it into "what should I order from whom, and how much" without buying inventory software. `invopt` does that with textbook formulas that you can read, check by hand and reproduce: every number in the output can be traced back to [docs/formulas.md](docs/formulas.md).

## Features

- ABC (consumption value) and XYZ (weekly demand variability) classification.
- Safety stock, reorder point and economic order quantity per SKU, with lead-time variability.
- Order recommendations that respect minimum order quantity and case packs.
- Status per SKU: DEAD, CRITICAL, REORDER, OVERSTOCK or OK.
- One purchase-order draft per supplier (CSV and Markdown), with safe file names on Windows, macOS and Linux.
- Reports as Markdown, a self-contained HTML page with inline SVG charts, JSON, CSV or Excel.
- Row-numbered validation messages for bad input files.
- Deterministic results: the reference date defaults to the latest sale, never today's date.
- A deterministic synthetic data generator for trying it out.

## Installation

```bash
pip install git+https://github.com/kevin-vasilescu/inventory-optimizer.git
```

With Excel output:

```bash
pip install "inventory-optimizer[excel] @ git+https://github.com/kevin-vasilescu/inventory-optimizer.git"
```

From source:

```bash
git clone https://github.com/kevin-vasilescu/inventory-optimizer.git
cd inventory-optimizer
pip install -e ".[excel]"
```

## 60-second quickstart

Generate sample data, analyze it, then write purchase orders. This is the real output of these commands:

```console
$ invopt sample --skus 10 --days 100 --seed 21 --out data
Wrote data/sales.csv
Wrote data/inventory.csv

$ invopt analyze data/sales.csv data/inventory.csv --top 5 --out report.md
Inventory analysis as of 2026-06-30 (10 SKUs)

Status counts
  DEAD           0
  CRITICAL       3
  REORDER        1
  OVERSTOCK      1
  OK             5

Total inventory value:              2,372.48
Dead-stock value:                       0.00
Capital for recommended orders:     5,571.10

Top 4 urgent SKUs
sku                    supplier               status                 on_hand                reorder_point          days_of_cover          recommended_order_qty
SKU-0005               Nordic Supply Co       CRITICAL               0                      9                      0                      76
SKU-0010               Harbor Goods           CRITICAL               1                      7                      2.8125                 51
SKU-0004               Blue River Trading     CRITICAL               14                     60                     4.5985                 378
SKU-0001               Acme Wholesale         REORDER                4                      9                      10.2857                77

Report written to report.md

$ invopt po data/sales.csv data/inventory.csv --out purchase_orders
Acme Wholesale: 1 line(s), total 421.96
Blue River Trading: 1 line(s), total 2,286.90
Harbor Goods: 1 line(s), total 2,027.76
Nordic Supply Co: 1 line(s), total 834.48
Wrote 8 file(s) to purchase_orders
```

An excerpt of the generated `report.md`:

```markdown
## Key figures

| Metric | Value |
|---|---|
| SKUs analysed | 10 |
| Inventory value | 2,372.48 |
| Dead-stock value | 0.00 |
| Overstock value | 62.10 |
| Capital needed for recommended orders | 5,571.10 |
| Status CRITICAL | 3 |

## ABC x XYZ matrix (SKU counts)

| ABC \ XYZ | X | Y | Z |
|---|---|---|---|
| A | 3 | 0 | 1 |
| B | 0 | 0 | 2 |
| C | 0 | 0 | 4 |
```

The `make examples` target regenerates a full set of example reports (Markdown, HTML, Excel and purchase orders) in `examples/`.

## Python API

```python
from inventory_optimizer import Config, analyze, load_inventory, load_sales

sales = load_sales("data/sales.csv")
inventory = load_inventory("data/inventory.csv")
result = analyze(sales, inventory, Config(service_level=0.97))

print(result.summary()["status_counts"])
plan = result.reorder_plan()          # pandas DataFrame, most urgent first
orders = result.purchase_orders()     # {supplier: DataFrame}
result.to_html()                      # also to_markdown(), to_json(), to_excel(path)
```

## CLI reference

| Command | Purpose |
|---|---|
| `invopt analyze SALES INVENTORY` | Print a summary; with `--out` write a report. Options: `--as-of`, `--lookback-days`, `--service-level`, `--holding-cost-rate`, `--default-order-cost`, `--format md\|html\|json\|csv\|xlsx`, `--out`, `--status`, `--top` |
| `invopt po SALES INVENTORY --out DIR` | One CSV and one Markdown purchase-order draft per supplier. Extra option: `--supplier` |
| `invopt validate SALES INVENTORY` | Check both files and list problems with row numbers |
| `invopt sample --out DIR` | Generate synthetic data. Options: `--skus`, `--days`, `--seed` |
| `invopt --version` | Print the version |

Exit codes: 0 success, 1 data or validation error (or missing optional dependency), 2 usage error. Details are in [docs/usage.md](docs/usage.md).

## Input format

`sales.csv` (required):

| Column | Type | Notes |
|---|---|---|
| `date` | YYYY-MM-DD | |
| `sku` | text | |
| `quantity` | number >= 0 | Rows for the same SKU and day are summed |

`inventory.csv` (required, one row per SKU):

| Column | Type | Default |
|---|---|---|
| `sku` | text, unique | required |
| `description` | text | empty |
| `category` | text | `Uncategorized` |
| `supplier` | text | required |
| `unit_cost` | number > 0 | required |
| `on_hand` | number >= 0 | required |
| `on_order` | number >= 0 | 0 |
| `lead_time_days` | number > 0 | required |
| `lead_time_std_days` | number >= 0 | 0 |
| `moq` | number > 0 | 1 |
| `case_pack` | number > 0 | 1 |
| `order_cost` | number >= 0 | `--default-order-cost` (50) |

## Formulas

Safety stock is `ceil(z * sqrt(LT * sigma_d^2 + d^2 * sigma_LT^2))`, the reorder point is `ceil(d * LT + unrounded safety stock)`, and EOQ is `ceil(sqrt(2 * D * S / H))`. Every formula, with a worked example, is in [docs/formulas.md](docs/formulas.md).

## Development

```bash
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
pre-commit install
make test
```

`make lint`, `make typecheck` and `make build` run Ruff, mypy and the package build.

## Limitations

- Assumes demand over the lead time is roughly normally distributed. Intermittent or very lumpy items will be less accurate.
- Single location only: no multi-echelon or multi-warehouse logic.
- No perishables, shelf life or expiry handling.
- No supplier price breaks or volume discounts; EOQ uses one flat unit cost.
- Demand history is used as is: no trend, seasonality or promotion adjustment.

## Roadmap

- Forecasting beyond a flat average (trend and seasonality).
- Supplier price breaks and order consolidation across SKUs.
- Per-SKU service levels, for example by ABC class.
- Published releases on PyPI.

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md). Please follow the [Code of Conduct](CODE_OF_CONDUCT.md) and report security issues as described in [SECURITY.md](SECURITY.md).

## License

MIT. See [LICENSE](LICENSE).
