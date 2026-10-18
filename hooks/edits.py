#!/usr/bin/env python3
"""PreToolUse guard for edits: refuses new text that crosses a hard line a machine can check."""

from __future__ import annotations

import json
import os
import re
import sys
from typing import Any

LONG_DASH = re.compile("[" + chr(0x2014) + chr(0x2013) + "]")
SUPPRESSION = re.compile(
    r"#\s*noqa\b|#\s*pylint:\s*disable|#\s*type:\s*ignore|eslint-disable|@ts-ignore|@ts-nocheck|//\s*nolint|#\s*nosec\b",
    re.I,
)
SILENT_SKIP = re.compile(
    r"^[ \t]*(?:if|elif|except)\b[^\n#]*:[ \t]*"
    r"(?:(?:#[^\n]*)?\n[ \t]*)?(?:pass|continue)[ \t]*(?:#[^\n]*)?$",
    re.M,
)
PYTHON_SUFFIXES = {".py", ".pyi"}
COMMENT_MARKERS = {
    **{suffix: "#" for suffix in (".py", ".pyi", ".sh", ".bash", ".zsh", ".tf", ".rb")},
    **{suffix: "//" for suffix in (".js", ".jsx", ".mjs", ".cjs", ".ts", ".tsx", ".go", ".rs", ".java", ".kt")},
    **{suffix: "//" for suffix in (".c", ".h", ".cpp", ".hpp", ".php", ".swift")},
    ".sql": "--",
}


def stacked_comments(text: str, marker: str) -> int:
    """Count the comment lines that directly follow another comment line, a shebang aside."""
    lines = [line.lstrip() for line in text.split("\n")]
    comments = [line.startswith(marker) and not line.startswith("#!") for line in lines]
    return sum(1 for above, below in zip(comments, comments[1:]) if above and below)


def findings(path: str, old: str, new: str) -> list[str]:
    """Return the hard lines the new text crosses that the old text did not."""
    suffix = os.path.splitext(path)[1].lower()
    marker = COMMENT_MARKERS.get(suffix, "")
    found: list[str] = []
    if len(LONG_DASH.findall(new)) > len(LONG_DASH.findall(old)):
        found.append("adds a long dash: use a hyphen, a comma or a colon")
    if marker and len(SUPPRESSION.findall(new)) > len(SUPPRESSION.findall(old)):
        found.append("adds a lint suppression: fix the code instead")
    if marker and stacked_comments(new, marker) > stacked_comments(old, marker):
        found.append("adds a comment over one line: keep it to one line, or drop it")
    if suffix in PYTHON_SUFFIXES and len(SILENT_SKIP.findall(new)) > len(SILENT_SKIP.findall(old)):
        found.append("adds a silent skip: report the skip, or put the work under the condition")
    return found


def on_disk(path: str) -> str:
    """Return the text a file holds now, or nothing when it does not exist yet."""
    if not os.path.isfile(path):
        return ""
    with open(path, encoding="utf-8", errors="replace") as handle:
        return handle.read()


def before_and_after(tool: str, tool_input: dict[str, Any], path: str) -> tuple[str, str]:
    """Return the text an edit replaces and the text it puts in its place."""
    if tool == "Edit":
        return tool_input.get("old_string", ""), tool_input.get("new_string", "")
    if tool == "Write":
        return on_disk(path), tool_input.get("content", "")
    if tool == "NotebookEdit":
        return "", tool_input.get("new_source", "")
    return "", ""


def main() -> int:
    """Read the PreToolUse event from stdin and block an edit that adds what the hard lines forbid."""
    event = json.load(sys.stdin)
    tool_input = event.get("tool_input", {})
    path = tool_input.get("file_path") or tool_input.get("notebook_path") or ""
    old, new = before_and_after(event.get("tool_name", ""), tool_input, path)
    found = findings(path, old, new)
    if found:
        print(f"scapegoat: the edit to `{path}` {'; '.join(found)}.", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
