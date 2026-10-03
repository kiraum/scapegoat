"""The plugin's files agree with each other and keep the repo's own rules."""

from __future__ import annotations

import json
import os
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SKIPPED_DIRS = {".git", "results", "__pycache__"}
TEXT_SUFFIXES = {".md", ".json", ".yaml", ".yml", ".py", ".sh", ".txt"}
LONG_DASHES = (chr(0x2014), chr(0x2013))


def hook_commands(event: str) -> list[str]:
    """Return the shell commands the plugin registers for a hook event."""
    hooks = json.loads((ROOT / "hooks" / "hooks.json").read_text(encoding="utf-8"))["hooks"]
    return [hook["command"] for entry in hooks[event] for hook in entry["hooks"]]


class PluginTest(unittest.TestCase):
    """The wiring between the manifest, the hooks and the skill."""

    def test_the_session_hook_prints_the_rules_without_the_frontmatter(self) -> None:
        """The rules live in one file, and the hook prints its body."""
        (command,) = hook_commands("SessionStart")
        environment = {**os.environ, "CLAUDE_PLUGIN_ROOT": str(ROOT)}
        printed = subprocess.run(
            ["sh", "-c", command], env=environment, capture_output=True, text=True, check=True
        ).stdout
        self.assertTrue(printed.lstrip().startswith("# Scapegoat"))
        self.assertNotIn("argument-hint", printed)

    def test_the_guard_hook_fails_closed(self) -> None:
        """If the guard cannot run, the command is blocked rather than waved through."""
        (command,) = hook_commands("PreToolUse")
        self.assertIn("hooks/guard.py", command)
        self.assertTrue(command.endswith("|| exit 2"))

    def test_no_long_dash_in_the_repo(self) -> None:
        """The repo keeps its own rule: no long dashes in any text file."""
        files = [
            path
            for path in ROOT.rglob("*")
            if path.is_file() and path.suffix in TEXT_SUFFIXES and not SKIPPED_DIRS.intersection(path.parts)
        ]
        offenders = [
            str(path.relative_to(ROOT))
            for path in files
            if any(dash in path.read_text(encoding="utf-8") for dash in LONG_DASHES)
        ]
        self.assertEqual(offenders, [])
