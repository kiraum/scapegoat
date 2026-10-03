#!/usr/bin/env bash
# Seeds a page with its own stylesheet and script, for a visual change.
set -euo pipefail

git init -q -b main
git config user.name fixture
git config user.email fixture@example.com

mkdir -p templates static/css static/js

cat > templates/page.html <<'HTML'
<link rel="stylesheet" href="/static/css/page.css">
<p class="balance">Balance: <span id="balance" data-value="{{ balance }}">{{ balance }}</span></p>
<script src="/static/js/page.js"></script>
HTML

cat > static/css/page.css <<'CSS'
.balance {
  font-weight: 600;
}
CSS

cat > static/js/page.js <<'JS'
function showBalance(value) {
  document.getElementById("balance").textContent = value.toFixed(2);
}
JS

git add -A
git commit -q -m "feat(page): the page shows the balance"
