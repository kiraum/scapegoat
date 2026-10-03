#!/usr/bin/env bash
# Seeds an invoice that formats money with a shared helper, and a receipt that does not print money yet.
set -euo pipefail

git init -q -b main
git config user.name fixture
git config user.email fixture@example.com

mkdir -p app

cat > app/__init__.py <<'PY'
"""Documents."""
PY

cat > app/money.py <<'PY'
"""Money formatting shared by every document."""


def format_amount(value: float) -> str:
    """Return an amount the way every document prints it: two decimals and the currency code."""
    return f"{value:,.2f} EUR"
PY

cat > app/invoice.py <<'PY'
"""Invoice lines."""

from app.money import format_amount


def invoice_lines(items: list[dict]) -> list[str]:
    """Return one line per item, then the total."""
    lines = [f"{item['name']}: {format_amount(item['price'] * item['qty'])}" for item in items]
    total = sum(item["price"] * item["qty"] for item in items)
    return [*lines, f"Total: {format_amount(total)}"]
PY

cat > app/receipt.py <<'PY'
"""Receipt lines."""


def receipt_lines(items: list[dict]) -> list[str]:
    """Return one line per item, name then quantity."""
    return [f"{item['name']} x{item['qty']}" for item in items]
PY

git add -A
git commit -q -m "feat(invoice): the invoice prints every amount through one formatter"
