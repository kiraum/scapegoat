---
type: regex
target: { source: file, path: templates/page.html }
pattern: '<script(?![^>]*\bsrc=)'
match: not_contains
---
