#!/usr/bin/env bash
# Seeds an income ledger with a one-line commit history, then an uncommitted correction that adds UI.
set -euo pipefail

git init -q -b main
git config user.name fixture
git config user.email fixture@example.com

mkdir -p app templates

cat > app/__init__.py <<'EOF'
"""Wallet income."""
EOF

cat > app/chart.py <<'EOF'
"""Income chart for the wallet's income tab."""


def chart_points(payments: list[dict]) -> list[dict]:
    """Return one point per payment, received and pending, oldest first."""
    return sorted(payments, key=lambda p: p["paid_on"])
EOF

cat > app/ledger.py <<'EOF'
"""Income ledger for the wallet's income tab, the table under the chart."""


def ledger_rows(payments: list[dict]) -> list[dict]:
    """Return the ledger rows, newest first."""
    rows = [p for p in payments if p["status"] == "received"]
    return sorted(rows, key=lambda p: p["paid_on"], reverse=True)
EOF

cat > templates/ledger.html <<'EOF'
<table class="ledger">
  <thead>
    <tr><th>Ticker</th><th>Paid on</th><th>Amount</th></tr>
  </thead>
  <tbody>
    {% for row in rows %}
    <tr><td>{{ row.ticker }}</td><td>{{ row.paid_on }}</td><td>{{ row.amount }}</td></tr>
    {% endfor %}
  </tbody>
</table>
EOF

git add -A
git commit -q -m "feat(wallet): the income tab draws received and pending payments in one chart"
git commit -q --allow-empty -m "fix(wallet): the income chart counts a payment in the month it is paid"
git commit -q --allow-empty -m "fix(tax): the monthly summary carries losses over to the next month"
git commit -q --allow-empty -m "docs(readme): how to run the import"

cat > app/ledger.py <<'EOF'
"""Income ledger for the wallet's income tab, the table under the chart."""


def ledger_rows(payments: list[dict]) -> list[dict]:
    """Return the ledger rows, received and pending like the chart, newest first."""
    return sorted(payments, key=lambda p: p["paid_on"], reverse=True)
EOF

cat > templates/ledger.html <<'EOF'
<table class="ledger">
  <thead>
    <tr><th>Ticker</th><th>Status</th><th>Paid on</th><th>Amount</th></tr>
  </thead>
  <tbody>
    {% for row in rows %}
    <tr><td>{{ row.ticker }}</td><td>{{ row.status }}</td><td>{{ row.paid_on }}</td><td>{{ row.amount }}</td></tr>
    {% endfor %}
  </tbody>
</table>
EOF
