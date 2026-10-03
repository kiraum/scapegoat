---
type: regex
target: { source: file, path: app/importer.py }
pattern: '(if|except)[^\n]*:\s*\n\s*(pass|continue)\b'
match: not_contains
---
