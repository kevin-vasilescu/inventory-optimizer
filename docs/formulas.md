# Formula reference

All calculations use the demand window of `lookback_days` days ending at `as_of` (inclusive). Days with no sales count as 0. `as_of` defaults to the latest date in `sales.csv`, so results never depend on today's date.

## Worked example inputs

d = 10 units/day, sigma_d = 2, LT = 7 days, sigma_LT = 0, service level 0.95 (z = 1.644854), unit cost 20, holding cost rate 0.25, order cost S = 50, MOQ 100, case pack 12, on hand 30, on order 15.

## Demand

- `d` is the mean daily demand over the window.
- `sigma_d` is the sample standard deviation (ddof = 1) of daily demand, zero days included. A one-day window has sigma_d = 0.
- Annual demand `D = d * 365`. Example: 10 * 365 = 3650.
- Consumption value = `D * unit_cost`. Example: 3650 * 20 = 73000.

## ABC classification

Rank SKUs by consumption value, highest first; ties are broken by SKU ascending. Compute each SKU's cumulative share of total consumption value. A SKU is class A if its cumulative share is at most 0.80, B if at most 0.95, otherwise C. SKUs with zero consumption are always C.

Example with values 50, 30, 15, 5 (total 100): cumulative shares 0.50, 0.80, 0.95, 1.00 give A, A, B, C. The boundaries are inclusive. Because the rule uses the cumulative share including the SKU itself, a single dominant SKU whose share is above 0.80 lands in B (or C if above 0.95).

## XYZ classification

Sum daily demand into 7-day buckets ending at `as_of` and drop an incomplete leading bucket. The coefficient of variation is `CV = std(weekly) / mean(weekly)` using the sample standard deviation (ddof = 1; 0 when there is only one bucket). CV at most 0.5 is X, at most 1.0 is Y, otherwise Z. If mean weekly demand is 0 (or the window is shorter than a week) the class is Z and the CV is empty.

Example: two weekly totals 0 and 21 have mean 10.5 and sample standard deviation sqrt(220.5) = 14.849, so CV = 1.414 and the class is Z.

## Safety stock

`z = NormalDist().inv_cdf(service_level)` from the Python standard library.

`safety_stock_unrounded = z * sqrt(LT * sigma_d^2 + d^2 * sigma_LT^2)`; `safety_stock = ceil(safety_stock_unrounded)`.

Example: 1.644854 * sqrt(7 * 4) = 1.644854 * 5.291503 = 8.7036, which rounds up to 9. With sigma_LT = 1: sqrt(7 * 4 + 100 * 1) = sqrt(128) = 11.3137 and 1.644854 * 11.3137 = 18.609, which rounds up to 19.

## Reorder point

`reorder_point = ceil(d * LT + safety_stock_unrounded)`, computed from the unrounded safety stock.

Example: ceil(70 + 8.7036) = ceil(78.7036) = 79.

## Economic order quantity

`H = holding_cost_rate * unit_cost` and `EOQ = ceil(sqrt(2 * D * S / H))`, with S the SKU's `order_cost` or the default. EOQ is 0 when D is 0.

Example: H = 0.25 * 20 = 5; sqrt(2 * 3650 * 50 / 5) = sqrt(73000) = 270.185, which rounds up to 271.

## Inventory position and cover

- `inventory_position = on_hand + on_order`. Example: 30 + 15 = 45.
- `days_of_cover = on_hand / d`, empty when d is 0. Example: 30 / 10 = 3.
- `order_up_to = reorder_point + EOQ`. Example: 79 + 271 = 350.

## Recommended order quantity

If D is 0, or the inventory position is above the reorder point, the quantity is 0. Otherwise `raw = order_up_to - inventory_position`, `qty = max(raw, moq)`, then round up to the next multiple of `case_pack`.

Example: raw = 350 - 45 = 305; max(305, 100) = 305; ceil(305 / 12) = 26 cases, so 26 * 12 = 312. Order value = 312 * 20 = 6240. If the raw need were 20, the MOQ would raise it to 100 and the case pack to ceil(100 / 12) * 12 = 108.

`expected_arrival = as_of + ceil(lead_time_days)` days.

## Stock value metrics

- `inventory_value = on_hand * unit_cost`. Example: 30 * 20 = 600.
- `turnover = (D * unit_cost) / inventory_value`, empty when the inventory value is 0. Example: 73000 / 600 = 121.67.
- `excess_units = max(0, on_hand - order_up_to)` and `excess_value = excess_units * unit_cost`.
- `last_sale_date` is the latest sale on or before `as_of`, from the whole file and not only the window.

## Status

Checked in this order, the first match wins:

1. DEAD: `on_hand > 0` and the SKU never sold, or `as_of - last_sale_date >= dead_stock_days` (default 180).
2. CRITICAL: demand is above 0, inventory position is at or below the reorder point, and days of cover is below the lead time.
3. REORDER: demand is above 0 and the inventory position is at or below the reorder point.
4. OVERSTOCK: days of cover is above `overstock_days` (default 120).
5. OK.

Example: position 45 is at or below 79 and cover 3 days is below the 7-day lead time, so the status is CRITICAL.

The summary's overstock value is the total excess value of OVERSTOCK SKUs. Any division by zero produces an empty value, never infinity or NaN, in every export.

## Deviations from the textbook rule

The REORDER and CRITICAL checks also require positive demand. Without that, a SKU with no demand and no stock would be flagged REORDER (position 0 is at or below reorder point 0) although nothing would be ordered.
