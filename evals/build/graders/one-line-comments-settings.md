---
type: regex
target: { source: file, path: app/settings.py }
pattern: '^[ \t]*#.*\n[ \t]*#'
flags: m
match: not_contains
---
