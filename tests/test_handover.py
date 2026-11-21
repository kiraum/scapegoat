"""The handover check sends a reply back once when it edited files in a repo and ends without Commit and Tag."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Optional

HANDOVER = Path(__file__).resolve().parent.parent / "hooks" / "handover.py"
COMMIT = "Commit:\n```\nfix(search): an empty query returns no rows instead of every row\n```"
TAG = "Tag:\n```\ngit tag -a v1.0.1 -m 'v1.0.1'\n```"
ASK = (
    "**WRITE ACTION: I WILL RUN `git push origin main`. IT PUBLISHES 2 COMMITS TO THE REMOTE. REPLY YES TO AUTHORIZE.**"
)


def human(text: str) -> dict[str, object]:
    """Build a transcript entry for a message the owner typed."""
    return {"type": "user", "isSidechain": False, "origin": {"kind": "human"}, "message": {"content": text}}


def assistant(text: str) -> dict[str, object]:
    """Build a transcript entry for text Claude wrote."""
    return {"type": "assistant", "isSidechain": False, "message": {"content": [{"type": "text", "text": text}]}}


def edit(path: str, sidechain: bool = False) -> dict[str, object]:
    """Build the transcript entry Claude, or a subagent, leaves when it edits a file."""
    call = {"type": "tool_use", "id": "edit", "name": "Edit", "input": {"file_path": path, "new_string": "rows"}}
    return {"type": "assistant", "isSidechain": sidechain, "message": {"content": [call]}}


def transcript(entries: Sequence[Mapping[str, object]]) -> str:
    """Write a session transcript to a temporary file and return its path."""
    with tempfile.NamedTemporaryFile("w", suffix=".jsonl", delete=False, encoding="utf-8") as handle:
        handle.write("\n".join(json.dumps(entry) for entry in entries) + "\n")
    return handle.name


def folder(files: Mapping[str, str], git: bool = True) -> Path:
    """Create a temporary directory holding the given files, as a git repo unless told otherwise."""
    root = Path(tempfile.mkdtemp())
    if git:
        subprocess.run(["git", "init", "-q", str(root)], check=True)
    for name, content in files.items():
        (root / name).write_text(content, encoding="utf-8")
    return root


def changed_file() -> str:
    """Return the path of a file git reports as changed, in a fresh repo."""
    return str(folder({"search.py": "rows = []\n"}) / "search.py")


def event(transcript_path: str, reply: Optional[str] = None, active: bool = False) -> str:
    """Build the Stop event Claude Code sends when a reply ends."""
    fields: dict[str, object] = {"hook_event_name": "Stop", "stop_hook_active": active}
    if reply is not None:
        fields["last_assistant_message"] = reply
    return json.dumps({**fields, "transcript_path": transcript_path})


def run_handover(payload: str) -> subprocess.CompletedProcess[str]:
    """Run the handover check the way the hook does, with the event on stdin."""
    return subprocess.run([sys.executable, str(HANDOVER)], input=payload, capture_output=True, text=True, check=False)


def ended(reply: str, path: str, earlier: Sequence[Mapping[str, object]] = ()) -> subprocess.CompletedProcess[str]:
    """Run the check on a turn in which the owner asks, Claude edits one file and then replies."""
    entries = [*earlier, human("fix the search"), edit(path), assistant(reply)]
    return run_handover(event(transcript(entries), reply))


class SentBackTest(unittest.TestCase):
    """A reply that changed a file in a repo ends with Commit and Tag, or is sent back for them."""

    def test_a_reply_without_commit_and_tag_is_sent_back(self) -> None:
        """The block names the file that changed and both missing parts."""
        result = ended("Fixed.", changed_file())
        self.assertEqual(result.returncode, 2)
        self.assertIn("scapegoat: this reply edited `search.py`", result.stderr)
        self.assertIn("without Commit and Tag", result.stderr)

    def test_only_the_missing_part_is_named(self) -> None:
        """A reply with a commit message and no tag is sent back for the tag alone."""
        result = ended(f"Fixed.\n{COMMIT}", changed_file())
        self.assertEqual(result.returncode, 2)
        self.assertIn("without Tag", result.stderr)

    def test_the_reply_is_read_from_the_transcript_when_the_event_carries_none(self) -> None:
        """An older Claude Code sends no reply text, so the turn's own text is judged."""
        entries = [human("fix the search"), edit(changed_file()), assistant("Fixed.")]
        result = run_handover(event(transcript(entries)))
        self.assertEqual(result.returncode, 2)
        self.assertIn("without Commit and Tag", result.stderr)


class PassesTest(unittest.TestCase):
    """What the handover check lets end."""

    def assert_passes(self, result: subprocess.CompletedProcess[str]) -> None:
        """Fail unless the check ran clean and let the reply end."""
        self.assertEqual((result.returncode, result.stderr), (0, ""))

    def test_a_reply_with_commit_and_tag_passes(self) -> None:
        """The handover is there, so the reply ends."""
        self.assert_passes(ended(f"Fixed.\n{COMMIT}\n{TAG}", changed_file()))

    def test_a_tag_that_waits_for_another_step_counts(self) -> None:
        """A tag labelled with the step it waits for is still a tag handed over."""
        waiting = TAG.replace("Tag:", "Tag, after the merge:")
        self.assert_passes(ended(f"Fixed.\n{COMMIT}\n{waiting}", changed_file()))

    def test_a_reply_that_edited_nothing_passes(self) -> None:
        """An answer is not a handover, even while the repo holds uncommitted work."""
        changed_file()
        self.assert_passes(run_handover(event(transcript([human("why?"), assistant("Because.")]), "Because.")))

    def test_an_edit_from_an_earlier_turn_does_not_count(self) -> None:
        """Only what this reply changed asks for a handover."""
        entries = [human("fix it"), edit(changed_file()), assistant("Fixed."), human("why?"), assistant("Because.")]
        self.assert_passes(run_handover(event(transcript(entries), "Because.")))

    def test_a_file_outside_a_repo_passes(self) -> None:
        """With no repo there is nothing to commit or tag."""
        path = str(folder({"notes.md": "draft\n"}, git=False) / "notes.md")
        self.assert_passes(ended("Noted.", path))

    def test_a_file_git_ignores_passes(self) -> None:
        """A file git does not track or report is not part of a commit."""
        path = str(folder({".gitignore": "scratch.txt\n", "scratch.txt": "draft\n"}) / "scratch.txt")
        self.assert_passes(ended("Noted.", path))

    def test_a_subagent_edit_does_not_count(self) -> None:
        """A subagent hands over to Claude, not to the owner."""
        entries = [human("fix the search"), edit(changed_file(), sidechain=True), assistant("Fixed.")]
        self.assert_passes(run_handover(event(transcript(entries), "Fixed.")))

    def test_a_reply_already_sent_back_once_passes(self) -> None:
        """The check asks once: a second block could loop on a reply that has a reason to differ."""
        entries = [human("fix the search"), edit(changed_file()), assistant("Fixed.")]
        self.assert_passes(run_handover(event(transcript(entries), "Fixed.", active=True)))

    def test_a_write_action_ask_passes(self) -> None:
        """The ask has to be the last line of its reply, so nothing is added after it."""
        self.assert_passes(ended(f"Fixed.\n{ASK}", changed_file()))

    def test_the_phrase_that_stops_the_rules_stops_the_check(self) -> None:
        """Once the owner switches the rules off, the handover is no longer asked for."""
        earlier = [human("Stop blaming the goat."), assistant("The rules are off.")]
        self.assert_passes(ended("Fixed.", changed_file(), earlier))


class MentionTest(unittest.TestCase):
    """The phrase counts only as a whole message, the way a yes does."""

    def test_a_message_that_only_mentions_the_phrase_does_not_stop_the_check(self) -> None:
        """A longer message may be talking about the phrase, so the check stays on."""
        earlier = [human("call it stop blaming the goat\n\nrelease 0.3.1"), assistant("Renamed.")]
        result = ended("Fixed.", changed_file(), earlier)
        self.assertEqual(result.returncode, 2)
        self.assertIn("without Commit and Tag", result.stderr)


class UnreadableTest(unittest.TestCase):
    """A reply that cannot be checked still ends, and the owner is told."""

    def test_a_missing_transcript_is_reported_and_does_not_block(self) -> None:
        """Any exit code but 0 and 2 shows the message without holding the reply."""
        result = run_handover(event("/nonexistent/transcript.jsonl", "Fixed."))
        self.assertEqual(result.returncode, 1)
        self.assertIn("scapegoat: no session transcript", result.stderr)

    def test_a_broken_event_is_an_error_and_does_not_block(self) -> None:
        """Input the check cannot read is reported, never passed in silence and never held."""
        result = run_handover("not json")
        self.assertEqual(result.returncode, 1)
        self.assertNotEqual(result.stderr, "")


if __name__ == "__main__":
    unittest.main()
