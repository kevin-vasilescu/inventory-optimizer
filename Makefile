.PHONY: install test lint format typecheck build examples

install:
	pip install -e ".[dev]"

test:
	pytest --cov=inventory_optimizer --cov-report=term-missing --cov-fail-under=90

lint:
	ruff check .

format:
	ruff format .

typecheck:
	mypy --strict src

build:
	python -m build
	twine check dist/*

examples:
	invopt sample --skus 10 --days 100 --seed 21 --out examples
	invopt analyze examples/sales.csv examples/inventory.csv --out examples/report.md
	invopt analyze examples/sales.csv examples/inventory.csv --format html --out examples/report.html
	invopt analyze examples/sales.csv examples/inventory.csv --format xlsx --out examples/report.xlsx
	invopt po examples/sales.csv examples/inventory.csv --out examples/purchase_orders
