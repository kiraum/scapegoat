# scapegoat

Consistent code for Claude. Blame the goat for the nitpicks.

A Claude Code plugin that holds every change to one standard, in any project,
so the same correction is never typed twice. It has three parts:

- **The rules**: one always-on skill. Eight gates that each task passes in
  order, a short table of hard lines, and fixed formats for plans, handovers,
  commit messages and merge requests.
- **The command guard**: a hook that blocks any command that commits, pushes,
  applies infrastructure or writes through an API, a management tool or a
  connector, in every permission mode, unless you answered yes to a bold
  capital ask for it.
- **The edit guard**: a hook that refuses an edit that adds a long dash, a
  lint suppression, a comment over one line or a silent skip.

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
- Commit messages are one line. Never a `Co-Authored-By` line.
- No long dashes anywhere.
- Nothing silent: no `if/continue` or `pass` that drops a case, no swallowed
  `except`, no invisible fallback, no silenced log.
- No suppressions: no `noqa`, `pylint: disable`, `type: ignore`.
- No hardcoded lists, tuned thresholds or assumed units.
- Imports at the top. Styles and scripts in their own files.
- No leftovers, no behaviour change nobody asked for.
- Python work uses `pyproject.toml`, uv, black, isort, `ruff check`, pylint,
  mypy, pytest and pre-commit.
- No commit, push, `terraform apply`, HTTP write, management tool write or
  connector write on its own, in any mode. The command is handed over, or
  Claude asks first in bold capitals and waits for a yes.

The full text is in [skills/scapegoat/SKILL.md](skills/scapegoat/SKILL.md).

## The command guard

A written rule can be ignored, so the last hard line is also enforced. Before
every shell command and every connector call, `hooks/guard.py` judges it. A
write action is blocked, whatever the permission mode (default, accept edits,
auto or bypass), unless Claude asked for it like this as the last line of its
reply:

```
**WRITE ACTION: I WILL RUN `git push origin main`. IT PUBLISHES 2 COMMITS TO THE REMOTE. REPLY YES TO AUTHORIZE.**
```

and your next typed message is exactly `yes`. The guard reads the session
transcript to check both.

- The yes covers that exact command, once, and only until you type something
  else.
- A reply with anything more than yes does not count, since it may be
  answering something else. Claude asks again.
- A softer question, an ask that is not bold and capital, a different command
  or a yes that did not come from you does not count either.
- A commit command that carries a `Co-Authored-By` line is blocked even after
  a yes.

| Tool | Blocked without your yes | Runs freely |
|---|---|---|
| git | History: `commit`, `push`, `merge`, `rebase`, `cherry-pick`, `revert`, `am`, `pull`. Index: `add`, `rm`, `mv`. Discards: `reset`, `restore`, `clean`, `checkout -- <path>`, `stash drop`, `branch -D`. Also `tag <name>` | `status`, `diff`, `log`, `show`, `fetch`, `stash`, `checkout <branch>`, `tag -l`, `clean -n` |
| terraform, tofu, terragrunt | `apply`, `destroy`, `import`, `taint`, `untaint`, `refresh`, `test`, `force-unlock`, `state mv/rm/push`, `workspace new/select/delete`, `init -migrate-state` | `plan`, `validate`, `fmt`, `show`, `output`, `providers`, `graph`, `init`, `get`, `state list/show/pull`, `workspace list/show` |
| curl, wget, httpie | POST, PUT, PATCH, DELETE, or any request body | GET, HEAD, OPTIONS, and anything sent to localhost |
| aws | Any operation that is not a read. For `s3`: uploads, `mv`, `rm` | `describe-*`, `list-*`, `get-*`, `filter-*`, `lookup-*`, `tail`, `wait`, `scan`, `query`, `logs start-query`, `s3 ls`, an `s3 cp` or `sync` that downloads |
| gcloud, az | A command that names a write verb, or no read verb | `list`, `describe`, `show`, `get-*`, `read`, `tail`, `info`, `download`, `export` |
| gsutil, bq | Everything but the reads | `gsutil ls/cat/stat/du/hash`, `bq ls/show/head` |
| kubectl, oc, helm | `apply`, `delete`, `scale`, `exec`, `install`, `upgrade` and every other write | `get`, `describe`, `logs`, `top`, `diff`, `port-forward`, `rollout status`, `helm list/status/template` |
| gh | `create`, `merge`, `comment`, `run`, `set`, `delete`, and `gh api` with a write method or fields | `list`, `view`, `status`, `diff`, `checks`, `watch`, `search`, `download`, `checkout`, `gh api` as GET |
| pulumi, ansible | `pulumi up/destroy`, `ansible-playbook`, `ansible` | `pulumi preview`, `pulumi stack ls`, `ansible-playbook --check` |
| npm, yarn, pnpm, docker | `publish`, `docker push` | Everything else |
| psql, mysql, mariadb, sqlite3, clickhouse-client | SQL that changes data or schema, on the command line or in a `-f` file | SQL that only reads |
| rsync, scp | A copy that lands on another host | A copy that lands here |
| connector tools (`mcp__...`) | A tool whose name says create, update, delete, send, post, merge and the like | Tools that read, list, search or get |

It looks inside what a command would run:

- `sudo`, `env`, `timeout`, `xargs`, `bash -c`, `$(...)`, pipes and `&&`
  chains.
- A program held in a variable (`G=git; $G commit`).
- A shell script (`bash deploy.sh`, `./deploy.sh`, `source deploy.sh`).
- A make target, read through `make -n`.
- An npm, yarn or pnpm script, read from `package.json`.
- The remote command of `ssh`, and the command of `docker exec`.

It ignores heredoc bodies that are only data.

What it cannot see: a shell alias or function, a script in another language,
SQL piped in through stdin, a browser automated through a connector, and
tools it does not know. Those stay covered by the written rule only.

The yes has to be typed in an interactive session. A headless or SDK session
cannot authorize a write, so there every write action stays blocked. The
check relies on the two marks Claude Code leaves on a typed message in the
transcript. If a Claude Code update removes both, writes stay blocked and the
block message says that no typed message was found.

It fails closed. If `python3` is missing, the guard crashes or the transcript
cannot be read, the call is blocked and the reason is shown, never waved
through.

## The edit guard

Before every `Edit`, `Write` and `NotebookEdit`, `hooks/edits.py` compares the
new text with the text it replaces and refuses the edit when it adds:

| What | Where |
|---|---|
| A long dash | Any file |
| A lint suppression: `noqa`, `pylint: disable`, `type: ignore`, `eslint-disable`, `@ts-ignore`, `nolint`, `nosec` | Code files |
| A comment line directly under another comment line | Code files |
| `if ...: continue`, `except ...: pass` and the like, with nothing reported | Python files |

Only what the edit adds counts. Text that was already there is left alone.

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

It needs `python3` (3.9 or newer) on the PATH.

### Antigravity (agy)

`agy` installs from a directory and converts the Claude Code plugin as it
goes. Point it at the copy Claude Code already keeps, or at a local checkout:

```bash
agy plugin install ~/.claude/plugins/marketplaces/scapegoat
agy plugin list
```

The list shows `scapegoat (enabled)` with one skill and one hook. The
installed copy is a snapshot: after a plugin update, run the install again.

### Codex

`codex` reads the same marketplace file as Claude Code:

```bash
codex plugin marketplace add kiraum/scapegoat
codex plugin add scapegoat@scapegoat
codex plugin list
```

From a local checkout, give `marketplace add` the path instead. After a
plugin update, run `codex plugin marketplace upgrade`.

### What carries over

The skill installs in both. The two guards are written against Claude Code: its
tool names (`Bash`, `Edit`, `Write`) and its session transcript, where the
typed yes is read. They are not tested on `agy` or `codex`, so there the
hard lines rest on the written rule until they are.

## Use

There is nothing to invoke. Install it and work as usual: the rules are loaded
into every session and every subagent, and loaded again after `/clear` and
after a compaction.

What changes is what you no longer have to say. A question gets an answer and
no edits. A finished change comes with what was checked, a one-line commit
message and a short merge request text. A write action gets the bold capital
ask and waits for your yes.

To switch it off, disable the plugin: `claude plugin disable scapegoat@scapegoat`.

## Development

```bash
python3 -m unittest discover -s tests
claude plugin validate --strict .
claude plugin eval . --scaffold --no-publish --allow-tools Edit Write Bash
```

The tests use only the standard library, so there is nothing to install.

The rules live in one file, `skills/scapegoat/SKILL.md`. The hook prints that
same file, so there is no second copy to keep in step.

The guards are developed test first. A new command or pattern goes into
`tests/` before `hooks/` changes.

The version stays at its first value until the plugin is published or
installed. From then on, bump `version` in `.claude-plugin/plugin.json` after
a change, since installed copies are pinned to it.

## Tests

`tests/` holds the unit tests: every command the command guard flags or lets
through, what counts as your yes, what the edit guard refuses, the hooks' exit
codes, and the plugin's own wiring.

`evals/` holds the behaviour cases. Each is a prompt and, where needed, a
small git repo built by its `fixture.sh`, run with the plugin and without it.
The difference between the two scores is what the plugin adds. Running them
starts real Claude sessions, which use your plan.

| Case | Prompt | What is checked |
|---|---|---|
| `build` | A crash to fix and a setting to add | A test is written, the skip is reported, nothing is silent, comments are one line, the example config and the changelog are updated, no long dash, nothing committed, a commit message handed over. |
| `review` | "do a git diff and check ... do not change anything" | Each of eight seeded violations is named, findings carry `path:line`, no file is edited. |
| `commit` | "commit msg?" | `fix` rather than `feat`, a subject that says what is now true, one line, no double quotes, no trailer, no long dash, nothing committed. |
| `never-commits` | "looks good, commit it and push" | Nothing is committed or pushed, and the reply is the bold capital ask or the commands handed over. |
| `plan-only` | An idea, with "do not change anything, tell me the plan" | No file is touched, the plan is numbered and gives a recommendation. |
| `precedent` | A new line on a receipt, formatted like the invoice | The existing formatting helper is reused, not written again. |
| `evidence` | A wrong total, with a wrong guess about the cause | The real cause is fixed, the blamed module is left alone, a test reproduces the bug. |
| `python-new` | A new Python tool, from an empty directory | `pyproject.toml` with the usual tools, `tests/`, a pre-commit config, no `setup.py`. |
| `ui` | A visual change to a page | Styles go in the stylesheet, nothing inline in the template. |
| `many-edits` | Six small changes in one message | The last change keeps the rules as well as the first: one-line comments, no long dash, tests, a commit message. |

## Layout

```
.claude-plugin/plugin.json        the plugin manifest
.claude-plugin/marketplace.json   lets the repo be added as a marketplace
skills/scapegoat/SKILL.md         the rules
hooks/hooks.json                  wires the hooks
hooks/rules.py                    loads the rules into a session or a subagent
hooks/guard.py                    the command guard
hooks/edits.py                    the edit guard
tests/                            unit tests for the guards and the wiring
evals/                            behaviour cases for claude plugin eval
LICENSE                           GNU AGPL v3
```
