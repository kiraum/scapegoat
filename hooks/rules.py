#!/usr/bin/env python3
"""Puts the skill's rules in context at the start of a session, and of every subagent."""

from __future__ import annotations

import json
import sys
from pathlib import Path

SKILL = Path(__file__).resolve().parent.parent / "skills" / "scapegoat" / "SKILL.md"


def rules() -> str:
    """Return the skill's body, without its frontmatter."""
    return SKILL.read_text(encoding="utf-8").split("\n---\n", 1)[1].strip()


def main() -> int:
    """Print the rules as plain text for a session, or as added context for a subagent, which takes only JSON."""
    event = json.load(sys.stdin)
    if event.get("hook_event_name") == "SubagentStart":
        added = {"hookEventName": "SubagentStart", "additionalContext": rules()}
        print(json.dumps({"hookSpecificOutput": added}))
    else:
        print(rules())
    return 0


if __name__ == "__main__":
    sys.exit(main())
