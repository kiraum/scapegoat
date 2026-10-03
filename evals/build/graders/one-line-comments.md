---
type: regex
target: { source: file, path: app/importer.py }
pattern: '^[ \t]*#.*\n[ \t]*#'
flags: m
match: not_contains
---
