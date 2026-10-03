"""The edit guard refuses new text that adds a long dash, a lint suppression, a stacked comment or a silent skip."""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from collections.abc import Mapping
from pathlib import Path
from types import ModuleType

EDITS = Path(__file__).resolve().parent.parent / "hooks" / "edits.py"
DASH = chr(0x2014)


def load_edits() -> ModuleType:
    """Load the edit guard from its file, so the tests need no install and no path setup."""
    spec = importlib.util.spec_from_file_location("edits", EDITS)
    if spec is None or spec.loader is None:
        raise ImportError(str(EDITS))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


findings = load_edits().findings


def run_edits(payload: str) -> subprocess.CompletedProcess[str]:
    """Run the edit guard the way the hook does, with the event on stdin."""
    return subprocess.run([sys.executable, str(EDITS)], input=payload, capture_output=True, text=True, check=False)


def event(tool: str, tool_input: Mapping[str, object]) -> str:
    """Build the PreToolUse event Claude Code sends to a hook."""
    return json.dumps({"hook_event_name": "PreToolUse", "tool_name": tool, "tool_input": tool_input})


class FindingsTest(unittest.TestCase):
    """What the edit guard finds in the text an edit adds."""

    def test_a_long_dash_is_refused_in_any_file(self) -> None:
        """Prose and code alike: the dash is never added."""
        self.assertTrue(findings("README.md", "", f"fast {DASH} and small"))
        self.assertTrue(findings("app.py", "x = 1", f'x = "a {DASH} b"'))

    def test_a_long_dash_that_was_already_there_is_left_alone(self) -> None:
        """Text nobody is adding is not this edit's fault."""
        self.assertEqual(findings("README.md", f"old {DASH} text", f"old {DASH} text, edited"), [])

    def test_a_suppression_is_refused_in_code(self) -> None:
        """Silencing a finding is not a fix, in any of the usual spellings."""
        added = {
            "app.py": ["x = f()  # noqa: E501", "import y  # pylint: disable=unused-import", "v = g()  # type: ignore"],
            "app.ts": ["// eslint-disable-next-line no-console", "// @ts-ignore"],
        }
        for path, lines in added.items():
            for line in lines:
                with self.subTest(line=line):
                    self.assertTrue(findings(path, "", line + "\n"))

    def test_a_suppression_named_in_prose_is_fine(self) -> None:
        """A document may talk about the markers it forbids."""
        self.assertEqual(findings("README.md", "", "Never add `# noqa` to silence a finding.\n"), [])

    def test_a_comment_over_one_line_is_refused(self) -> None:
        """Two comment lines in a row are one comment over two lines, whatever the language's marker."""
        stacked = {
            "app.py": "# first line\n# second line\nx = 1\n",
            "app.js": "// first line\n// second line\nlet x;\n",
            "report.sql": "-- first line\n-- second line\nselect 1;\n",
        }
        for path, text in stacked.items():
            with self.subTest(path=path):
                self.assertTrue(findings(path, "", text))

    def test_separate_one_line_comments_are_fine(self) -> None:
        """Comments apart from each other, and one under a shebang, are each one line."""
        self.assertEqual(findings("app.py", "", "# one\nx = 1\n# two\ny = 2\n"), [])
        self.assertEqual(findings("tool.py", "", "#!/usr/bin/env python3\n# the tool\nx = 1\n"), [])

    def test_a_comment_block_that_was_already_there_is_left_alone(self) -> None:
        """Comments the edit did not write stay as they are."""
        self.assertEqual(findings("app.py", "# a\n# b\nx = 1\n", "# a\n# b\nx = 2\n"), [])

    def test_a_silent_skip_is_refused_in_python(self) -> None:
        """A case dropped with continue or pass, and nothing said, is the bug that hides."""
        skips = [
            "for row in rows:\n    if not row:\n        continue\n",
            "try:\n    f()\nexcept ValueError:\n    pass\n",
            "for row in rows:\n    if not row: continue\n",
        ]
        for text in skips:
            with self.subTest(text=text):
                self.assertTrue(findings("app.py", "", text))

    def test_a_reported_skip_is_fine(self) -> None:
        """A skip that is reported first is allowed to move on."""
        text = "for row in rows:\n    if not row:\n        report.skip(row)\n        continue\n"
        self.assertEqual(findings("app.py", "", text), [])


class HookTest(unittest.TestCase):
    """How the edit guard behaves when Claude Code runs it as a hook."""

    def test_an_edit_that_adds_a_long_dash_is_blocked(self) -> None:
        """Exit code 2 blocks the edit, and stderr says what to change."""
        edit = {"file_path": "/tmp/notes.md", "old_string": "a", "new_string": f"a {DASH} b"}
        result = run_edits(event("Edit", edit))
        self.assertEqual(result.returncode, 2)
        self.assertIn("/tmp/notes.md", result.stderr)
        self.assertIn("long dash", result.stderr)

    def test_a_clean_edit_passes(self) -> None:
        """Nothing to say about an edit that crosses no line."""
        result = run_edits(event("Edit", {"file_path": "/tmp/app.py", "old_string": "x = 1", "new_string": "x = 2"}))
        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stderr, "")

    def test_a_write_is_compared_with_the_file_on_disk(self) -> None:
        """Rewriting a file that already had a dash is fine; a new file with a suppression is not."""
        with tempfile.NamedTemporaryFile("w", suffix=".md", delete=False, encoding="utf-8") as handle:
            handle.write(f"old {DASH} text\n")
        kept = run_edits(event("Write", {"file_path": handle.name, "content": f"old {DASH} text\nmore\n"}))
        self.assertEqual(kept.returncode, 0)
        fresh = {"file_path": str(Path(tempfile.gettempdir()) / "scapegoat-new.py"), "content": "x = f()  # noqa\n"}
        self.assertEqual(run_edits(event("Write", fresh)).returncode, 2)

    def test_a_notebook_cell_is_checked_too(self) -> None:
        """New cell source is new text like any other."""
        cell = {"notebook_path": "/tmp/analysis.ipynb", "new_source": f"total {DASH} sum"}
        self.assertEqual(run_edits(event("NotebookEdit", cell)).returncode, 2)

    def test_other_tools_are_ignored(self) -> None:
        """Only edits are judged here."""
        self.assertEqual(run_edits(event("Read", {"file_path": "/tmp/app.py"})).returncode, 0)

    def test_the_hook_fails_loudly_on_input_it_cannot_read(self) -> None:
        """A broken event is an error, never a silent pass."""
        result = run_edits("not json")
        self.assertNotEqual(result.returncode, 0)
        self.assertNotEqual(result.stderr, "")
