# Usage

## Commands

```
invopt analyze SALES_CSV INVENTORY_CSV [--as-of YYYY-MM-DD] [--lookback-days N]
               [--service-level 0.95] [--holding-cost-rate 0.25] [--default-order-cost 50]
               [--format md|html|json|csv|xlsx] [--out PATH] [--status CRITICAL,REORDER,...] [--top N]
invopt po SALES_CSV INVENTORY_CSV --out DIR [--supplier NAME] [same options as analyze]
invopt validate SALES_CSV INVENTORY_CSV
invopt sample [--skus 200] [--days 365] [--seed 42] --out DIR
invopt --version
```

`analyze` always prints a terminal summary. `--out` writes the full report in the chosen `--format` (default `md`). `--status` keeps only SKUs with those statuses, and the summary then describes only the kept SKUs. `--format xlsx` needs `--out` and the optional extra: `pip install "inventory-optimizer[excel]"`.

`po` writes `PO_<supplier>_<as_of>.csv` and `.md` for every supplier that has something to order. Supplier names are sanitized for file names (only letters, digits, dot, dash and underscore remain) and reserved Windows names are avoided. The CSV ends with a `TOTAL` row.

## Exit codes

| Code | Meaning |
|---|---|
| 0 | Success |
| 1 | Data or validation error, or the optional Excel dependency is missing |
| 2 | Usage error: invalid option value, unknown status or supplier, bad `--as-of` |

Expected errors print a short message and never a traceback.

## Validation

Errors (exit 1) carry row numbers; row 1 is the header. Checked: missing required columns, empty file, unparsable dates, negative or non-numeric quantity, non-positive `unit_cost`, `lead_time_days`, `moq` or `case_pack`, negative `on_hand`, `on_order`, `lead_time_std_days` or `order_cost`, duplicate SKUs in the inventory, and empty SKU or supplier.

Warnings (analysis continues): SKUs in sales but not in inventory are ignored; SKUs in inventory with no sales get zero demand; fewer than 28 days of history in the lookback window; `as_of` earlier than the latest sale, in which case later sales are ignored.

## JSON schema

`--format json` writes an object with these keys, in this order:

- `as_of`: ISO date.
- `config`: lookback_days, service_level, holding_cost_rate, default_order_cost, abc_thresholds, xyz_thresholds, dead_stock_days, overstock_days.
- `summary`: as_of, sku_count, inventory_value, dead_stock_value, overstock_value, capital_needed, status_counts, abc_xyz.
- `warnings`: list of strings.
- `skus`: one object per SKU with the columns listed below.

Undefined values are `null`. Numbers that are whole are written as integers; others are rounded to 4 decimals. Dates are `YYYY-MM-DD`.

## CSV schema

`--format csv` writes the `skus` table with this header, one row per SKU, and empty cells for undefined values:

`sku, description, category, supplier, abc_class, xyz_class, avg_daily_demand, demand_std_daily, annual_demand, consumption_value, weekly_cv, unit_cost, on_hand, on_order, inventory_position, lead_time_days, safety_stock, reorder_point, eoq, order_up_to, days_of_cover, status, recommended_order_qty, order_value, expected_arrival, last_sale_date, inventory_value, turnover, excess_units, excess_value`

## Python API

`load_sales(path)` and `load_inventory(path)` return pandas DataFrames and raise `DataError` (with a `problems` list) on invalid input. `analyze(sales, inventory, config=Config())` returns an `AnalysisResult` with `.to_dataframe()`, `.summary()`, `.reorder_plan()`, `.purchase_orders()`, `.to_json()`, `.to_csv()`, `.to_markdown()`, `.to_html()` and `.to_excel(path)`. In `.to_dataframe()`, undefined values are NaN or None; every export turns them into null or empty cells.
