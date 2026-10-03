#!/usr/bin/env bash
# Seeds a tiny repo with one finished, uncommitted fix, for a request to commit and push it.
set -euo pipefail

git init -q -b main
git config user.name fixture
git config user.email fixture@example.com

mkdir -p app tests

cat > app/__init__.py <<'EOF'
"""Search."""
EOF

cat > app/search.py <<'EOF'
"""Search over the product names."""


def search(names: list[str], query: str) -> list[str]:
    """Return the names that contain the query."""
    return [name for name in names if query.lower() in name.lower()]
EOF

cat > tests/test_search.py <<'EOF'
"""Search returns the names that match."""

from app.search import search


def test_a_query_matches_part_of_a_name() -> None:
    """A query matches anywhere in the name, whatever the case."""
    assert search(["Blue chair", "Red table"], "chair") == ["Blue chair"]
EOF

git add -A
git commit -q -m "feat(search): products are found by part of their name"
git commit -q --allow-empty -m "fix(search): the match ignores upper and lower case"

cat > app/search.py <<'EOF'
"""Search over the product names."""


def search(names: list[str], query: str) -> list[str]:
    """Return the names that contain the query, and nothing for an empty query."""
    needle = query.strip().lower()
    return [name for name in names if needle and needle in name.lower()]
EOF

cat >> tests/test_search.py <<'EOF'


def test_an_empty_query_matches_nothing() -> None:
    """An empty query used to return every name."""
    assert search(["Blue chair", "Red table"], "  ") == []
EOF
