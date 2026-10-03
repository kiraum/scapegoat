---
type: regex
target: { source: file, path: app/text.py }
pattern: '^[ \t]*#.*\n[ \t]*#'
flags: m
match: not_contains
---
