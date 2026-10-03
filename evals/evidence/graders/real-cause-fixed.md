---
type: llm
focus: { source: file, path: app/totals.py }
---

PASS if monthly_total adds every line, including lines whose tax is 0.
FAIL if lines with a tax of 0 are still left out of the sum.
