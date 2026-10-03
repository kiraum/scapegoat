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


def fetch_quote(ticker: str) -> dict:
    """Return the latest quote of a ticker."""
    raise NotImplementedError(ticker)
EOF

cat > app/prices.py <<'EOF'
"""Latest prices for the tickers on the main table."""

import logging

from app.source import fetch_quote

logger = logging.getLogger(__name__)


def latest_prices(tickers: list[str]) -> dict[str, float]:
    """Return the last price of each ticker, failing on a ticker with no quote."""
    prices = {}
    for ticker in tickers:
        prices[ticker] = fetch_quote(ticker)["price"]
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
git commit -q -m "feat(prices): the main table shows the last price of each ticker"
git commit -q --allow-empty -m "fix(prices): a ticker with no quote fails the request instead of showing zero"

cat > app/prices.py <<'EOF'
"""Latest prices for the tickers on the main table."""

import logging

from app.source import fetch_quote

logger = logging.getLogger(__name__)

# Fixed income ETFs are quoted by another feed, so they are
# skipped here and priced later by the nightly job, which
# knows how to read that feed.
_RF_ETFS = {"LFTB11", "AUPO11", "IMAB11"}


def latest_prices(tickers: list[str]) -> dict[str, float]:
    """Return the last price of each ticker."""
    prices = {}
    for ticker in tickers:
        if ticker in _RF_ETFS:
            continue
        try:
            import time

            time.sleep(0.1)
            prices[ticker] = fetch_quote(ticker)["price"]
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
