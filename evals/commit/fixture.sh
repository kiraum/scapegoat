#!/usr/bin/env bash
# Seeds an orders page with a one-line commit history, then an uncommitted correction that adds UI.
set -euo pipefail

git init -q -b main
git config user.name fixture
git config user.email fixture@example.com

mkdir -p app templates

cat > app/__init__.py <<'EOF'
"""Orders page."""
EOF

cat > app/chart.py <<'EOF'
"""Orders chart, the top of the orders page."""


def chart_points(orders: list[dict]) -> list[dict]:
    """Return one point per order, paid and pending, oldest first."""
    return sorted(orders, key=lambda o: o["due_on"])
EOF

cat > app/table.py <<'EOF'
"""Orders table, under the chart on the orders page."""


def table_rows(orders: list[dict]) -> list[dict]:
    """Return the table rows, newest first."""
    rows = [o for o in orders if o["status"] == "paid"]
    return sorted(rows, key=lambda o: o["due_on"], reverse=True)
EOF

cat > templates/table.html <<'EOF'
<table class="orders">
  <thead>
    <tr><th>Customer</th><th>Due on</th><th>Amount</th></tr>
  </thead>
  <tbody>
    {% for row in rows %}
    <tr><td>{{ row.customer }}</td><td>{{ row.due_on }}</td><td>{{ row.amount }}</td></tr>
    {% endfor %}
  </tbody>
</table>
EOF

git add -A
git commit -q -m "feat(orders): the orders page draws paid and pending orders in one chart"
git commit -q --allow-empty -m "fix(orders): the chart counts an order in the month it is due"
git commit -q --allow-empty -m "fix(export): the monthly export carries open orders over to the next month"
git commit -q --allow-empty -m "docs(readme): how to run the export"

cat > app/table.py <<'EOF'
"""Orders table, under the chart on the orders page."""


def table_rows(orders: list[dict]) -> list[dict]:
    """Return the table rows, paid and pending like the chart, newest first."""
    return sorted(orders, key=lambda o: o["due_on"], reverse=True)
EOF

cat > templates/table.html <<'EOF'
<table class="orders">
  <thead>
    <tr><th>Customer</th><th>Status</th><th>Due on</th><th>Amount</th></tr>
  </thead>
  <tbody>
    {% for row in rows %}
    <tr><td>{{ row.customer }}</td><td>{{ row.status }}</td><td>{{ row.due_on }}</td><td>{{ row.amount }}</td></tr>
    {% endfor %}
  </tbody>
</table>
EOF
