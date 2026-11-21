#!/usr/bin/env python3
"""Stop hook: sends a reply back once when it edited files in a repo and ends without Commit and Tag."""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
from typing import Any

from guard import ASK, entry_text, is_typed, read_transcript

EDIT_TOOLS = {"Edit", "Write", "NotebookEdit"}
STOP_PHRASE = re.compile(r"\s*stop blaming the goat[.!]?\s*", re.I)
LABELS = {
    "Commit": re.compile(r"^\W*Commit\b[^\n]*:", re.M),
    "Tag": re.compile(r"^\W*Tag\b[^\n]*:", re.M),
}
GIT_SECONDS = 5
NAMED_FILES = 3


def this_turn(entries: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Return what followed the owner's last typed message, or everything when nothing was typed."""
    typed = [index for index, entry in enumerate(entries) if is_typed(entry)]
    return entries[typed[-1] + 1 :] if typed else entries


def edited_paths(entries: list[dict[str, Any]]) -> list[str]:
    """Return the files these entries edited, each once, in the order Claude touched them."""
    calls = [
        part.get("input", {})
        for entry in entries
        if entry.get("type") == "assistant" and isinstance(entry.get("message", {}).get("content"), list)
        for part in entry["message"]["content"]
        if isinstance(part, dict) and part.get("type") == "tool_use" and part.get("name") in EDIT_TOOLS
    ]
    paths = [call.get("file_path") or call.get("notebook_path") or "" for call in calls]
    return list(dict.fromkeys(path for path in paths if path))


def changed(path: str) -> bool:
    """Tell whether git reports the file as changed or new: one it ignores, or one outside a repo, is not."""
    folder = os.path.dirname(path)
    if not shutil.which("git") or not os.path.isdir(folder):
        return False
    status = subprocess.run(
        ["git", "-C", folder, "status", "--porcelain", "--", path],
        capture_output=True,
        text=True,
        timeout=GIT_SECONDS,
        check=False,
    )
    return status.returncode == 0 and bool(status.stdout.strip())


def missing(reply: str) -> list[str]:
    """Return the parts of a handover the reply does not carry."""
    return [label for label, pattern in LABELS.items() if not pattern.search(reply)]


def sent_back(paths: list[str], absent: list[str]) -> str:
    """Word the block for Claude: the files the reply changed and what its handover lacks."""
    names = ", ".join(f"`{os.path.basename(path)}`" for path in paths[:NAMED_FILES])
    more = f" and {len(paths) - NAMED_FILES} more" if len(paths) > NAMED_FILES else ""
    return (
        f"scapegoat: this reply edited {names}{more} and ends without {' and '.join(absent)}. "
        "Finish the handover: Commit, MR on a branch, and Tag, however small the change. "
        "Tag is the commands for the release this change makes, or none with the reason."
    )


def main() -> int:
    """Read the Stop event from stdin and send the reply back once when its handover is missing."""
    event = json.load(sys.stdin)
    if event.get("stop_hook_active"):
        return 0
    transcript_path = event.get("transcript_path", "")
    if not os.path.isfile(transcript_path):
        print(
            "scapegoat: no session transcript to read, so this reply was not checked for its handover.", file=sys.stderr
        )
        return 1
    entries = read_transcript(transcript_path)
    turn = this_turn(entries)
    said = "\n".join(entry_text(entry) for entry in turn if entry.get("type") == "assistant")
    reply = event.get("last_assistant_message") or said
    absent = missing(reply)
    stopped = any(STOP_PHRASE.fullmatch(entry_text(entry)) for entry in entries if is_typed(entry))
    if not absent or stopped or ASK.search(reply):
        return 0
    cwd = event.get("cwd") or "."
    edited = [path for path in (os.path.join(cwd, name) for name in edited_paths(turn)) if changed(path)]
    if not edited:
        return 0
    print(sent_back(edited, absent), file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main())
