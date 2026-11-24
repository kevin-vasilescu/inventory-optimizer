"""Command-line interface (``invopt``)."""

from __future__ import annotations

from datetime import date, datetime
from enum import Enum
from pathlib import Path
from typing import Annotated, NoReturn

import typer

from . import __version__
from .analysis import analyze
from .config import Config, ConfigError
from .io import load_inventory, load_sales, read_inventory, read_sales
from .models import STATUSES, AnalysisResult
from .purchase_orders import write_purchase_orders
from .report.data import export_frame
from .report.excel import MissingExtraError
from .report.markdown import money
from .sample_data import write_sample
from .validation import DataError

app = typer.Typer(
    add_completion=False,
    no_args_is_help=True,
    help="Turn sales history and stock levels into ABC/XYZ classes, reorder points, EOQ and purchase orders.",
)

MAX_PROBLEMS = 20


class Format(str, Enum):
    """Report formats."""

    md = "md"
    html = "html"
    json = "json"
    csv = "csv"
    xlsx = "xlsx"


def _fail(message: str, code: int) -> NoReturn:
    typer.echo(f"Error: {message}", err=True)
    raise typer.Exit(code)


def _data_error(exc: DataError) -> NoReturn:
    shown = exc.problems[:MAX_PROBLEMS]
    lines = "\n".join(f"  - {p}" for p in shown)
    extra = len(exc.problems) - len(shown)
    more = f"\n  ... and {extra} more" if extra > 0 else ""
    _fail(f"found {len(exc.problems)} problem(s):\n{lines}{more}", 1)


def _version(value: bool) -> None:
    if value:
        typer.echo(f"invopt {__version__}")
        raise typer.Exit()


@app.callback()
def main(
    version: Annotated[
        bool, typer.Option("--version", callback=_version, is_eager=True, help="Show version and exit.")
    ] = False,
) -> None:
    """Inventory optimizer."""


def _parse_date(value: str | None) -> date | None:
    if value is None:
        return None
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError:
        _fail(f"--as-of {value!r} is not a valid YYYY-MM-DD date", 2)


def _run(
    sales: Path,
    inventory: Path,
    as_of: str | None,
    lookback_days: int,
    service_level: float,
    holding_cost_rate: float,
    default_order_cost: float,
) -> AnalysisResult:
    try:
        config = Config(
            as_of=_parse_date(as_of),
            lookback_days=lookback_days,
            service_level=service_level,
            holding_cost_rate=holding_cost_rate,
            default_order_cost=default_order_cost,
        )
    except ConfigError as exc:
        _fail(str(exc), 2)
    try:
        return analyze(load_sales(sales), load_inventory(inventory), config)
    except DataError as exc:
        _data_error(exc)


SalesArg = Annotated[Path, typer.Argument(help="sales.csv (date, sku, quantity)")]
InventoryArg = Annotated[Path, typer.Argument(help="inventory.csv (one row per SKU)")]
AsOf = Annotated[str | None, typer.Option("--as-of", help="Reference date YYYY-MM-DD (default: latest sale).")]
Lookback = Annotated[int, typer.Option("--lookback-days", help="Demand window in days.")]
Service = Annotated[float, typer.Option("--service-level", help="Target service level in (0.5, 1).")]
Holding = Annotated[float, typer.Option("--holding-cost-rate", help="Annual holding cost fraction.")]
OrderCost = Annotated[float, typer.Option("--default-order-cost", help="Fixed cost per order.")]


def _print_summary(result: AnalysisResult, top: int) -> None:
    s = result.summary()
    typer.echo(f"Inventory analysis as of {s['as_of']} ({s['sku_count']} SKUs)")
    for warning in result.warnings:
        typer.echo(f"Warning: {warning}")
    typer.echo("\nStatus counts")
    for name, count in s["status_counts"].items():
        typer.echo(f"  {name:<10}{count:>6}")
    typer.echo(f"\nTotal inventory value:        {money(s['inventory_value']):>14}")
    typer.echo(f"Dead-stock value:             {money(s['dead_stock_value']):>14}")
    typer.echo(f"Capital for recommended orders: {money(s['capital_needed']):>12}")
    plan = result.reorder_plan().head(top)
    if len(plan):
        typer.echo(f"\nTop {len(plan)} urgent SKUs")
        columns = ["sku", "supplier", "status", "on_hand", "reorder_point", "days_of_cover", "recommended_order_qty"]
        clean = export_frame(plan[columns])
        typer.echo("  ".join(f"{c:<21}" for c in columns))
        for row in clean.itertuples(index=False):
            typer.echo("  ".join(f"{'-' if v is None else v!s:<21}" for v in row))
    else:
        typer.echo("\nNo SKU needs ordering.")


def _write_report(result: AnalysisResult, fmt: Format, out: Path) -> None:
    out.parent.mkdir(parents=True, exist_ok=True)
    if fmt is Format.xlsx:
        result.to_excel(out)
        return
    text = {
        Format.md: result.to_markdown,
        Format.html: result.to_html,
        Format.json: result.to_json,
        Format.csv: result.to_csv,
    }[fmt]()
    out.write_text(text, encoding="utf-8", newline="\n")


@app.command("analyze")
def analyze_cmd(
    sales: SalesArg,
    inventory: InventoryArg,
    as_of: AsOf = None,
    lookback_days: Lookback = 90,
    service_level: Service = 0.95,
    holding_cost_rate: Holding = 0.25,
    default_order_cost: OrderCost = 50.0,
    fmt: Annotated[Format, typer.Option("--format", help="Report format written to --out.")] = Format.md,
    out: Annotated[Path | None, typer.Option("--out", help="Write the full report here.")] = None,
    status: Annotated[str | None, typer.Option("--status", help="Comma-separated statuses to keep.")] = None,
    top: Annotated[int, typer.Option("--top", min=1, help="Urgent SKUs shown in the terminal.")] = 10,
) -> None:
    """Analyze inventory and print a summary; optionally write a full report."""
    wanted = [s.strip().upper() for s in status.split(",") if s.strip()] if status else []
    invalid = [s for s in wanted if s not in STATUSES]
    if invalid:
        _fail(f"unknown status {', '.join(invalid)}; choose from {', '.join(STATUSES)}", 2)
    if fmt is Format.xlsx and out is None:
        _fail("--format xlsx requires --out", 2)
    result = _run(sales, inventory, as_of, lookback_days, service_level, holding_cost_rate, default_order_cost)
    if wanted:
        result = result.filter_status(wanted)
    try:
        if out is not None:
            _write_report(result, fmt, out)
    except MissingExtraError as exc:
        _fail(str(exc), 1)
    _print_summary(result, top)
    if out is not None:
        typer.echo(f"\nReport written to {out}")


@app.command("po")
def po_cmd(
    sales: SalesArg,
    inventory: InventoryArg,
    out: Annotated[Path, typer.Option("--out", help="Folder for purchase-order drafts.")],
    supplier: Annotated[str | None, typer.Option("--supplier", help="Only this supplier.")] = None,
    as_of: AsOf = None,
    lookback_days: Lookback = 90,
    service_level: Service = 0.95,
    holding_cost_rate: Holding = 0.25,
    default_order_cost: OrderCost = 50.0,
) -> None:
    """Write one purchase-order draft (CSV and Markdown) per supplier."""
    result = _run(sales, inventory, as_of, lookback_days, service_level, holding_cost_rate, default_order_cost)
    orders = result.purchase_orders()
    if supplier is not None:
        if supplier not in set(result.frame["supplier"]):
            _fail(f"unknown supplier {supplier!r}", 2)
        orders = {k: v for k, v in orders.items() if k == supplier}
    if not orders:
        typer.echo("Nothing to order: no SKU is at or below its reorder point.")
        return
    paths = write_purchase_orders(orders, out, result.as_of)
    for name, lines in orders.items():
        typer.echo(f"{name}: {len(lines)} line(s), total {money(float(lines['line_total'].sum()))}")
    typer.echo(f"Wrote {len(paths)} file(s) to {out}")


@app.command("validate")
def validate_cmd(sales: SalesArg, inventory: InventoryArg) -> None:
    """Validate both files and list problems with row numbers."""
    sales_df, problems = read_sales(sales)
    inv_df, inv_problems = read_inventory(inventory)
    problems = problems + inv_problems
    if problems:
        _data_error(DataError(problems))
    assert sales_df is not None and inv_df is not None
    unknown = sorted(set(sales_df["sku"]) - set(inv_df["sku"]))
    silent = sorted(set(inv_df["sku"]) - set(sales_df["sku"]))
    if unknown:
        typer.echo(f"Warning: {len(unknown)} SKU(s) in sales are not in inventory and will be ignored")
    if silent:
        typer.echo(f"Warning: {len(silent)} SKU(s) in inventory have no sales and get zero demand")
    typer.echo(f"OK: {len(sales_df)} sales rows and {len(inv_df)} inventory rows are valid.")


@app.command("sample")
def sample_cmd(
    out: Annotated[Path, typer.Option("--out", help="Destination folder.")],
    skus: Annotated[int, typer.Option("--skus", min=1)] = 200,
    days: Annotated[int, typer.Option("--days", min=1)] = 365,
    seed: Annotated[int, typer.Option("--seed")] = 42,
) -> None:
    """Generate synthetic sales.csv and inventory.csv."""
    for path in write_sample(out, skus, days, seed):
        typer.echo(f"Wrote {path}")
