#!/usr/bin/env bash
# Seeds a small text module and its test, for six changes asked in one message.
set -euo pipefail

git init -q -b main
git config user.name fixture
git config user.email fixture@example.com

mkdir -p app tests

cat > app/__init__.py <<'PY'
"""Text helpers."""
PY

cat > app/text.py <<'PY'
"""Small helpers for text."""


def shout(text: str) -> str:
    """Return the text in upper case."""
    return text.upper()
PY

cat > tests/test_text.py <<'PY'
"""The text helpers do what their names say."""

from app.text import shout


def test_shout_upper_cases() -> None:
    """Shouting upper-cases every letter."""
    assert shout("hey") == "HEY"
PY

git add -A
git commit -q -m "feat(text): shout upper-cases a text"
