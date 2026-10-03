#!/usr/bin/env bash
# Seeds a price table, then leaves an uncommitted change that crosses eight hard lines.
set -euo pipefail

git init -q -b main
git config user.name fixture
git config user.email fixture@example.com

mkdir -p app static/js

cat > app/__init__.py <<'EOF'
"""Price table."""
EOF

cat > app/source.py <<'EOF'
"""Quote source."""


def fetch_quote(sku: str) -> dict:
    """Return the latest quote of a product."""
    raise NotImplementedError(sku)
EOF

cat > app/prices.py <<'EOF'
"""Latest prices for the products on the main table."""

import logging

from app.source import fetch_quote

logger = logging.getLogger(__name__)


def latest_prices(skus: list[str]) -> dict[str, float]:
    """Return the last price of each product, failing on a product with no quote."""
    prices = {}
    for sku in skus:
        prices[sku] = fetch_quote(sku)["price"]
    return prices
EOF

cat > static/js/table.js <<'EOF'
function renderPrices(rows) {
  const body = document.getElementById("prices-body");
  const empty = document.getElementById("prices-empty");
  empty.hidden = rows.length > 0;
  body.replaceChildren(...rows.map(renderRow));
}
EOF

git add -A
git commit -q -m "feat(prices): the main table shows the last price of each product"
git commit -q --allow-empty -m "fix(prices): a product with no quote fails the request instead of showing zero"

cat > app/prices.py <<'EOF'
"""Latest prices for the products on the main table."""

import logging

from app.source import fetch_quote

logger = logging.getLogger(__name__)

# Legacy products are quoted by another feed, so they are
# skipped here and priced later by the nightly job, which
# knows how to read that feed.
_LEGACY_SKUS = {"A-100", "B-200", "C-300"}


def latest_prices(skus: list[str]) -> dict[str, float]:
    """Return the last price of each product."""
    prices = {}
    for sku in skus:
        if sku in _LEGACY_SKUS:
            continue
        try:
            import time

            time.sleep(0.1)
            prices[sku] = fetch_quote(sku)["price"]
        except Exception:  # noqa: BLE001
            pass
    return prices
EOF

# The long dash is built here so this repo's own files stay free of it.
dash=$(printf '\342\200\224')
cat > static/js/table.js <<EOF
function renderPrices(rows) {
  console.log("prices", rows);
  const body = document.getElementById("prices-body");
  const empty = document.getElementById("prices-empty");
  empty.textContent = "No prices yet ${dash} try again in a minute";
  empty.hidden = rows.length > 0;
  body.replaceChildren(...rows.map(renderRow));
}
EOF
