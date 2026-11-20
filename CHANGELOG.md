# Changelog

## Unreleased
- the rules reach a session in full: they were cut to their first 2,000 characters once they passed 10,000
- a handover on a branch ends with a merge request subject and a description of three lines at most
- every handover suggests the next tag: a new feature raises the minor number, a fix the patch
- a changelog is kept in every repo, per tag and unreleased, unless a tool generates it
- tests go where the project keeps them, not always in `tests/`
- a suggestion is weighed in a line or two and built in the same reply
- the README has install steps for agy and codex
- the word pass or continue in a comment or a string no longer reads as a silent skip
- only an exact yes authorizes a write, more writes are caught, and edits that cross a hard line are refused
- never a Co-Authored-By line in a commit message
- a write action runs only after a bold capital ask and a typed yes, in every permission mode
- a hook refuses commits, pushes, applies and remote writes
- the plugin installs from the Claude CLI with its skill, session hook and evals
