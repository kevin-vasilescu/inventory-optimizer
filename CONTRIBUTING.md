# Contributing

Thanks for helping improve inventory-optimizer.

## Setup

```bash
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
pre-commit install
```

## Workflow

1. Open an issue for larger changes before starting.
2. Create a branch and keep each change focused.
3. Run `make lint` and `make test` before pushing.
4. Use Conventional Commit messages, for example `feat(policy): add per-class service levels`.
5. Open a pull request and fill in the template.

## Testing rules

Expected values in tests must be calculated by hand, with the arithmetic in a comment, and never copied from the output of the code under test. Keep the policy math in small pure functions so it can be tested directly.
