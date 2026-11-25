#!/usr/bin/env bash
# Seeds a rates sync whose fetch helper has no retries option, and a repo that states no provider limit.
set -euo pipefail

git init -q -b main
git config user.name fixture
git config user.email fixture@example.com

mkdir -p app

cat > app/__init__.py <<'PY'
"""Exchange rates."""
PY

cat > app/http.py <<'PY'
"""The one place the app talks HTTP."""

import urllib.request


def fetch(url: str, timeout: float = 5.0) -> bytes:
    """Return the body of a GET, or raise what urllib raises."""
    with urllib.request.urlopen(url, timeout=timeout) as response:
        return response.read()
PY

cat > app/sync.py <<'PY'
"""Keeps the stored exchange rates in step with the provider."""

import json
import logging
from pathlib import Path

from app.http import fetch

LOG = logging.getLogger(__name__)
PROVIDER = "https://rates.example.com/v2/latest"
STORE = Path("data/rates.json")


def sync_rates() -> dict[str, float]:
    """Fetch today's rates and store them, leaving the stored file alone when the provider fails."""
    try:
        body = fetch(PROVIDER)
    except OSError:
        LOG.exception("rates provider unreachable, keeping the stored rates")
        raise
    rates = json.loads(body)["rates"]
    STORE.parent.mkdir(parents=True, exist_ok=True)
    STORE.write_text(json.dumps(rates), encoding="utf-8")
    return rates
PY

cat > README.md <<'MD'
# Rates

Keeps the shop's exchange rates in step with the provider.
MD

git add -A
git commit -q -m "feat(rates): the stored exchange rates follow the provider"
