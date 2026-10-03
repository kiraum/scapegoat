# scapegoat

Consistent code for Claude. Blame the goat for the nitpicks.

A Claude Code plugin that holds every change to one standard, so the same
correction is never typed twice. It is one always-on skill: seven gates that
each task passes in order, a short table of hard lines, and fixed formats for
plans, handovers and commit messages.

## The gates

| # | Gate | The question it asks |
|---|---|---|
| 1 | Mandate | What exactly was asked? A plan, an opinion or a build, all of it and only it. |
| 2 | Evidence | Do I know, or am I guessing? |
| 3 | Precedent | How does this codebase already do it? |
| 4 | Substance | Is this the real fix, and is it honest? |
| 5 | Ripples | What else does this touch: docs, locales, changelog, env example, jobs? |
| 6 | Diff | Would the owner pass this diff without a comment? |
| 7 | Handover | Can the owner commit and deploy from this reply alone? |

## The hard lines

Checked on every change, whatever the task:

- Inline comments are one line. Docstrings may be longer.
- No long dashes anywhere.
- Nothing silent: no `if/continue` or `pass` that drops a case, no swallowed
  `except`, no invisible fallback, no silenced log.
- No suppressions: no `noqa`, `pylint: disable`, `type: ignore`.
- No hardcoded lists, tuned thresholds or assumed currency.
- Imports at the top. No CSS or JS inside templates. No user settings in
  `localStorage`.
- No leftovers, no behaviour change nobody asked for.
- Never commits, pushes or applies. It hands over the command and a one-line
  commit message.

The full text is in [skills/scapegoat/SKILL.md](skills/scapegoat/SKILL.md).

## Install

In Claude Code, from GitHub:

```
/plugin marketplace add kiraum/scapegoat
/plugin install scapegoat@scapegoat
```

From a local checkout, the same two commands with the path:

```
/plugin marketplace add /path/to/scapegoat
/plugin install scapegoat@scapegoat
```

From a shell:

```bash
claude plugin marketplace add kiraum/scapegoat
claude plugin install scapegoat@scapegoat
```

For one session, without installing:

```bash
claude --plugin-dir /path/to/scapegoat
```

The session hook needs `awk` on the PATH, which macOS and Linux have.

## Use

It is on from the first prompt. A SessionStart hook loads the rules at
startup, on resume, after `/clear` and after a compaction, which is when rules
usually get lost.

| Say | Get |
|---|---|
| "tell me the plan", "wdyt", "do not change anything" | Numbered options and one recommendation. No file is touched. |
| "check the git diff", or `/scapegoat:scapegoat review [range]` | One line per finding: `path:line: what is wrong, the fix`. |
| "commit msg", or `/scapegoat:scapegoat commit` | One line, `type(scope): subject`, matched to the repo's log. |
| "stop scapegoat" | Off for the session. |

## Change a rule

The rules live in one file, `skills/scapegoat/SKILL.md`. The hook prints that
same file, so there is no second copy to keep in step. After editing it:

```bash
claude plugin validate --strict .
claude plugin eval . --scaffold --no-publish --allow-tools Edit Write Bash
```

Then bump `version` in `.claude-plugin/plugin.json`, since installed copies
are pinned to it.

## Tests

`evals/` holds three cases. Each is a small git repo built by its `fixture.sh`
and a prompt in the owner's own words, run with the plugin and without it. The
difference between the two scores is what the plugin adds.

| Case | Prompt | What is checked |
|---|---|---|
| `build` | A crash to fix and a setting to add | The skip is reported, nothing is silent, comments are one line, the env example and the changelog are updated, no long dash, nothing committed, a commit message handed over. |
| `review` | "do a git diff and check ... do not change anything" | Each of eight seeded violations is named, findings carry `path:line`, no file is edited. |
| `commit` | "commit msg?" | `fix` rather than `feat`, a subject that says what is now true, one line, no double quotes, no long dash, nothing committed. |

## Layout

```
.claude-plugin/plugin.json        the plugin manifest
.claude-plugin/marketplace.json   lets the repo be added as a marketplace
skills/scapegoat/SKILL.md         the rules
hooks/hooks.json                  loads the rules at session start
evals/                            the test cases
```
