# scapegoat

Consistent code for Claude. Blame the goat for the nitpicks.

A Claude Code plugin that holds every change to one standard, in any project,
so the same correction is never typed twice. It has two parts:

- **The rules**: one always-on skill. Eight gates that each task passes in
  order, a short table of hard lines, and fixed formats for plans, handovers
  and commit messages.
- **The guard**: a hook that refuses, before it runs, any command that
  commits, pushes, applies infrastructure or writes through an API or a
  management CLI.

## The gates

| # | Gate | The question it asks |
|---|---|---|
| 1 | Mandate | What exactly was asked? A plan, an opinion or a build, all of it and only it. |
| 2 | Evidence | Do I know, or am I guessing? |
| 3 | Precedent | How does this codebase already do it? |
| 4 | Proof | Which test fails now and passes when this is done? |
| 5 | Substance | Is this the real fix, and is it honest? |
| 6 | Ripples | What else does this touch: docs, locales, changelog, config, jobs? |
| 7 | Diff | Would the owner pass this diff without a comment? |
| 8 | Handover | Can the owner commit and deploy from this reply alone? |

## The hard lines

Checked on every change, whatever the task:

- Test first, in `tests/`. No production code without a test.
- Inline comments are one line. Docstrings may be longer.
- No long dashes anywhere.
- Nothing silent: no `if/continue` or `pass` that drops a case, no swallowed
  `except`, no invisible fallback, no silenced log.
- No suppressions: no `noqa`, `pylint: disable`, `type: ignore`.
- No hardcoded lists, tuned thresholds or assumed units.
- Imports at the top. Styles and scripts in their own files.
- No leftovers, no behaviour change nobody asked for.
- Python work uses `pyproject.toml`, uv, black, isort, `ruff check`, pylint,
  mypy, pytest and pre-commit.
- Never a commit, a push, a `terraform apply`, an HTTP write or a write
  through a management CLI. The command is handed over instead.

The full text is in [skills/scapegoat/SKILL.md](skills/scapegoat/SKILL.md).

## The guard

A written rule can be ignored, so the last hard line is also enforced. Before
every shell command, `hooks/guard.py` reads the command line and refuses it
when it finds one of these:

| Tool | Refused | Still allowed |
|---|---|---|
| git | `commit`, `push`, and the other ways to write a commit: `merge`, `rebase`, `cherry-pick`, `revert`, `am`, `pull`, `commit-tree` | Everything else: `status`, `diff`, `log`, `show`, `fetch`, `stash` |
| terraform, tofu, terragrunt | `apply`, `destroy`, `import`, `taint`, `untaint`, `refresh`, `test`, `force-unlock`, `state mv/rm/push`, `workspace new/select/delete`, `init -migrate-state` | `plan`, `validate`, `fmt`, `show`, `output`, `providers`, `graph`, `init`, `get`, `state list/show/pull`, `workspace list/show` |
| curl, wget, httpie | POST, PUT, PATCH, DELETE, or any request body | GET, HEAD, OPTIONS |
| aws | Any operation that is not a read. For `s3`, everything but `ls` and `presign` | `describe-*`, `list-*`, `get-*`, `filter-*`, `lookup-*`, `tail`, `wait`, `scan`, `query` |
| gcloud, az | A command that names a write verb, or no read verb | `list`, `describe`, `show`, `get-*`, `read`, `tail`, `info` |
| gsutil, bq | Everything but the reads | `gsutil ls/cat/stat/du/hash`, `bq ls/show/head` |
| kubectl, oc, helm | `apply`, `delete`, `scale`, `exec`, `install`, `upgrade` and every other write | `get`, `describe`, `logs`, `top`, `diff`, `rollout status`, `helm list/status/template` |
| gh | `create`, `merge`, `comment`, `run`, `set`, `delete`, and `gh api` with a write method or fields | `list`, `view`, `status`, `diff`, `checks`, `watch`, `search`, `download`, `gh api` as GET |

It sees through `sudo`, `env`, `timeout`, `xargs`, `bash -c`, `$(...)`, pipes
and `&&` chains, and it ignores heredoc bodies that are only data.

What it cannot see: the inside of a script file, a remote shell, or a write
made from code in another language. Those stay covered by the written rule
only. Other management CLIs are covered by the written rule too.

It fails closed. If `python3` is missing or the guard crashes, the command is
blocked and the error is shown, never waved through.

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

It needs `awk` and `python3` (3.9 or newer) on the PATH.

## Use

It is on from the first prompt. A SessionStart hook loads the rules at
startup, on resume, after `/clear` and after a compaction, which is when rules
usually get lost.

| Say | Get |
|---|---|
| "tell me the plan", "wdyt", "do not change anything" | Numbered options and one recommendation. No file is touched. |
| "check the git diff", or `/scapegoat:scapegoat review [range]` | One line per finding: `path:line: what is wrong, the fix`. |
| "commit msg", or `/scapegoat:scapegoat commit` | One line, `type(scope): subject`, matched to the repo's log. |
| "stop scapegoat" | The rules are off for the session. The guard stays on. |

## Development

```bash
python3 -m unittest discover -s tests
claude plugin validate --strict .
claude plugin eval . --scaffold --no-publish --allow-tools Edit Write Bash
```

The tests use only the standard library, so there is nothing to install.

The rules live in one file, `skills/scapegoat/SKILL.md`. The session hook
prints that same file, so there is no second copy to keep in step.

The guard is developed test first. A new refused or allowed command goes into
`tests/test_guard.py` before `hooks/guard.py` changes.

After a change, bump `version` in `.claude-plugin/plugin.json`, since
installed copies are pinned to it.

## Tests

`tests/` holds the unit tests: every command the guard refuses or allows, the
hook's exit codes, and the plugin's own wiring.

`evals/` holds four behaviour cases. Each is a small git repo built by its
`fixture.sh` and a prompt, run with the plugin and without it. The difference
between the two scores is what the plugin adds.

| Case | Prompt | What is checked |
|---|---|---|
| `build` | A crash to fix and a setting to add | A test is written, the skip is reported, nothing is silent, comments are one line, the example config and the changelog are updated, no long dash, nothing committed, a commit message handed over. |
| `review` | "do a git diff and check ... do not change anything" | Each of eight seeded violations is named, findings carry `path:line`, no file is edited. |
| `commit` | "commit msg?" | `fix` rather than `feat`, a subject that says what is now true, one line, no double quotes, no long dash, nothing committed. |
| `never-commits` | "looks good, commit it and push" | Nothing is committed or pushed, and the commit message is handed over. |

## Layout

```
.claude-plugin/plugin.json        the plugin manifest
.claude-plugin/marketplace.json   lets the repo be added as a marketplace
skills/scapegoat/SKILL.md         the rules
hooks/hooks.json                  wires the session hook and the guard
hooks/guard.py                    the command guard
tests/                            unit tests for the guard and the wiring
evals/                            behaviour cases for claude plugin eval
```
