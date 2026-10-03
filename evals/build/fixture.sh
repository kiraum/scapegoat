#!/usr/bin/env bash
# Seeds a small import service: a skip reporter, a settings module, an example config and a changelog.
set -euo pipefail

git init -q -b main
git config user.name fixture
git config user.email fixture@example.com

mkdir -p app config

cat > app/__init__.py <<'EOF'
"""Supplier file import."""
EOF

cat > app/report.py <<'EOF'
"""Rows an import left out, shown in the import dialog."""


class ImportReport:
    """Collects every skipped row with its reason."""

    def __init__(self) -> None:
        self.skipped: list[tuple[int, str]] = []

    def skip(self, line: int, reason: str) -> None:
        """Record a row that was not imported."""
        self.skipped.append((line, reason))
EOF

cat > app/settings.py <<'EOF'
"""Settings read from the environment, each documented in config/app.env.example."""

import os

IMPORT_ENCODING = os.environ.get("IMPORT_ENCODING", "utf-8")
EOF

cat > app/importer.py <<'EOF'
"""Parses the supplier movements CSV into events."""

import csv

from app.report import ImportReport
from app.settings import IMPORT_ENCODING


def parse_movements(path: str, report: ImportReport) -> list[dict]:
    """Parse the movements file, reporting every row that is left out."""
    events = []
    with open(path, newline="", encoding=IMPORT_ENCODING) as handle:
        for line, row in enumerate(csv.DictReader(handle), start=2):
            if row["type"] in ("in", "out"):
                events.append({"sku": row["sku"], "type": row["type"], "qty": float(row["qty"])})
            else:
                report.skip(line, f"unknown type {row['type']}")
    return events
EOF

cat > config/app.env.example <<'EOF'
# Encoding of the supplier file
IMPORT_ENCODING=utf-8
EOF

cat > CHANGELOG.md <<'EOF'
# Changelog

## [Unreleased]

### Added
- **Supplier file import**: movements are read from the supplier CSV into events.

### Fixed
- **Unknown movement types**: a row whose type is neither in nor out is listed in the import report instead of being dropped.
EOF

cat > README.md <<'EOF'
# supplier-import

Reads the supplier movements CSV. Settings live in `config/app.env.example`.
EOF

git add -A
git commit -q -m "feat(import): the supplier movements file is parsed into events"
git commit -q --allow-empty -m "fix(import): a row with an unknown type is reported instead of dropped"
git commit -q --allow-empty -m "docs(readme): where the settings live"
