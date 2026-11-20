#!/usr/bin/env bash
# Seeds a tiny tagged repo on a fix branch with no changelog, for a bug fix that should end with release text.
set -euo pipefail

git init -q -b main
git config user.name fixture
git config user.email fixture@example.com

mkdir -p app tests

cat > app/__init__.py <<'PY'
"""Search."""
PY

cat > app/search.py <<'PY'
"""Search over the product names."""


def search(names: list[str], query: str) -> list[str]:
    """Return the names that contain the query."""
    return [name for name in names if query.lower() in name.lower()]
PY

cat > tests/test_search.py <<'PY'
"""Search returns the names that match."""

from app.search import search


def test_a_query_matches_part_of_a_name() -> None:
    """A query matches anywhere in the name, whatever the case."""
    assert search(["Blue chair", "Red table"], "chair") == ["Blue chair"]
PY

git add -A
git commit -q -m "feat(search): products are found by part of their name"
git tag v0.2.1
git checkout -q -b fix/empty-search
