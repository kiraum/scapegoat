"""The plugin's files agree with each other and keep the repo's own rules."""

from __future__ import annotations

import json
import os
import re
import subprocess
import unittest
from collections.abc import Mapping
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
SKIPPED_DIRS = {".git", "results", "__pycache__"}
TEXT_SUFFIXES = {".md", ".json", ".yaml", ".yml", ".py", ".sh", ".txt"}
LONG_DASHES = (chr(0x2014), chr(0x2013))


HOOK_OUTPUT_CAP = 10_000


def hook_commands(event: str, matcher: str = "") -> list[str]:
    """Return the shell commands registered for a hook event, picked by its matcher when there are several."""
    hooks: dict[str, Any] = json.loads((ROOT / "hooks" / "hooks.json").read_text(encoding="utf-8"))["hooks"]
    (entry,) = [entry for entry in hooks[event] if not matcher or entry.get("matcher") == matcher]
    return [hook["command"] for hook in entry["hooks"]]


def hook_command(event: str, matcher: str = "") -> str:
    """Return the first shell command registered for a hook event."""
    return hook_commands(event, matcher)[0]


def run_hook(
    command: str, event: Mapping[str, object], path: str = os.environ["PATH"]
) -> subprocess.CompletedProcess[str]:
    """Run a hook command the way Claude Code does: through a shell, with the event on stdin."""
    environment = {**os.environ, "CLAUDE_PLUGIN_ROOT": str(ROOT), "PATH": path}
    return subprocess.run(
        ["/bin/sh", "-c", command],
        input=json.dumps(event),
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )


class PluginTest(unittest.TestCase):
    """The wiring between the manifest, the hooks and the skill."""

    def test_a_session_gets_the_rules_without_the_frontmatter(self) -> None:
        """The rules live in one file, and the session hook prints its body."""
        printed = run_hook(hook_command("SessionStart"), {"hook_event_name": "SessionStart"}).stdout
        self.assertTrue(printed.startswith("# Scapegoat"))
        self.assertNotIn("name: scapegoat", printed)

    def test_a_subagent_gets_the_rules_as_added_context(self) -> None:
        """A subagent only receives context a hook hands over as JSON."""
        printed = run_hook(hook_command("SubagentStart"), {"hook_event_name": "SubagentStart"}).stdout
        output = json.loads(printed)["hookSpecificOutput"]
        self.assertEqual(output["hookEventName"], "SubagentStart")
        self.assertTrue(output["additionalContext"].startswith("# Scapegoat"))

    def test_the_rules_arrive_whole_in_pieces_under_the_hook_output_cap(self) -> None:
        """Claude Code cuts a hook output over 10,000 characters down to a preview, so no piece may reach it."""
        skill = (ROOT / "skills" / "scapegoat" / "SKILL.md").read_text(encoding="utf-8")
        for event in ("SessionStart", "SubagentStart"):
            with self.subTest(event=event):
                printed = [run_hook(command, {"hook_event_name": event}).stdout for command in hook_commands(event)]
                if event == "SubagentStart":
                    printed = [json.loads(text)["hookSpecificOutput"]["additionalContext"] for text in printed]
                self.assertTrue(all(0 < len(text) < HOOK_OUTPUT_CAP for text in printed), [len(t) for t in printed])
                delivered = "\n".join(printed)
                for line in skill.split("\n---\n", 1)[1].splitlines():
                    self.assertIn(line, delivered)

    def test_each_guard_is_wired_to_its_tools_and_fails_closed(self) -> None:
        """If a guard cannot run, the call is blocked rather than waved through."""
        wiring = {"Bash|mcp__.*": "hooks/guard.py", "Edit|Write|NotebookEdit": "hooks/edits.py"}
        for matcher, script in wiring.items():
            with self.subTest(matcher=matcher):
                command = hook_command("PreToolUse", matcher)
                self.assertIn(script, command)
                self.assertTrue(command.endswith("|| exit 2"))

    def test_a_missing_python_blocks_with_a_plain_message(self) -> None:
        """Without python3 the guard cannot judge, so it says so and blocks."""
        event = {"tool_name": "Bash", "tool_input": {"command": "ls"}}
        result = run_hook(hook_command("PreToolUse", "Bash|mcp__.*"), event, path="/nonexistent")
        self.assertEqual(result.returncode, 2)
        self.assertIn("python3 is not on the PATH", result.stderr)

    def test_the_handover_check_runs_when_a_reply_ends_and_never_fails_closed(self) -> None:
        """A check that blocked on its own failure would hold every reply, so without python3 the reply still ends."""
        command = hook_command("Stop")
        self.assertIn("hooks/handover.py", command)
        result = run_hook(command, {"hook_event_name": "Stop"}, path="/nonexistent")
        self.assertNotIn(result.returncode, (0, 2))

    def test_the_phrase_that_stops_the_rules_is_the_same_everywhere(self) -> None:
        """The rules name the phrase, so the README and the check that listens for it carry the same words."""
        skill = (ROOT / "skills" / "scapegoat" / "SKILL.md").read_text(encoding="utf-8")
        (phrase,) = re.findall(r'Off only when the owner says "([^"]+)"', skill)
        for name in ("README.md", "hooks/handover.py"):
            with self.subTest(file=name):
                self.assertIn(phrase, (ROOT / name).read_text(encoding="utf-8"))

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
