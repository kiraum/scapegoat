---
type: regex
target: { source: file, path: templates/page.html }
pattern: '<style|style='
match: not_contains
---
