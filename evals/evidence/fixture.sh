#!/usr/bin/env bash
# Seeds a total that drops tax-free lines, next to a cache that works and is about to be blamed.
set -euo pipefail

git init -q -b main
git config user.name fixture
git config user.email fixture@example.com

mkdir -p app

cat > app/__init__.py <<'PY'
"""Summary page."""
PY

cat > app/cache.py <<'PY'
"""A small in-memory cache with a time to live."""

import functools
import time


def cached(seconds: int):
    """Cache a function's results, per arguments, for a number of seconds."""

    def wrap(function):
        """Wrap the function with its own store."""
        store = {}

        @functools.wraps(function)
        def inner(*args):
            """Return the stored value while it is fresh, and compute it again once it is not."""
            hit = store.get(args)
            if hit and time.monotonic() - hit[0] < seconds:
                return hit[1]
            value = function(*args)
            store[args] = (time.monotonic(), value)
            return value

        return inner

    return wrap
PY

cat > app/totals.py <<'PY'
"""Monthly totals for the summary page."""

from app.cache import cached


@cached(seconds=300)
def monthly_total(lines: tuple[tuple[float, float], ...]) -> float:
    """Return the month's total: every line's net amount plus its tax."""
    return round(sum(net + net * tax for net, tax in lines if tax), 2)
PY

git add -A
git commit -q -m "feat(summary): the summary page shows the month's total"
