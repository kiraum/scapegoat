#!/usr/bin/env python3
"""Puts the skill's rules in context at the start of a session, and of every subagent."""

from __future__ import annotations

import json
import sys
from pathlib import Path

PIECE_CHARS = 9_500
SKILL = Path(__file__).resolve().parent.parent / "skills" / "scapegoat" / "SKILL.md"


def rules() -> str:
    """Return the skill's body, without its frontmatter."""
    return SKILL.read_text(encoding="utf-8").split("\n---\n", 1)[1].strip()


def sections(text: str) -> list[str]:
    """Cut the rules at each second-level heading, leaving the ones inside a code block alone."""
    found: list[list[str]] = [[]]
    fenced = False
    for line in text.splitlines():
        fenced = fenced != line.startswith("```")
        if line.startswith("## ") and not fenced:
            found.append([])
        found[-1].append(line)
    return ["\n".join(lines) for lines in found]


def pieces() -> list[str]:
    """Return the rules as whole sections packed into pieces that each fit under the 10,000 character hook output cap."""
    packed: list[str] = []
    for section in sections(rules()):
        if packed and len(packed[-1]) + len(section) < PIECE_CHARS:
            packed[-1] += "\n" + section
        else:
            packed.append(section)
    later = [f"# Scapegoat, part {number} of {len(packed)}\n\n{piece}" for number, piece in enumerate(packed[1:], 2)]
    return packed[:1] + later


def main() -> int:
    """Print one piece of the rules: plain text for a session, added context for a subagent, which takes only JSON."""
    event = json.load(sys.stdin)
    piece = pieces()[int(sys.argv[1]) - 1]
    if event.get("hook_event_name") == "SubagentStart":
        added = {"hookEventName": "SubagentStart", "additionalContext": piece}
        print(json.dumps({"hookSpecificOutput": added}))
    else:
        print(piece)
    return 0


if __name__ == "__main__":
    sys.exit(main())
