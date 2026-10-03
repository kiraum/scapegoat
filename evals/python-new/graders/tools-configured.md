---
type: regex
target: { source: file, path: pyproject.toml }
pattern: '(?=[\s\S]*black)(?=[\s\S]*isort)(?=[\s\S]*ruff)(?=[\s\S]*mypy)(?=[\s\S]*pytest)'
---
