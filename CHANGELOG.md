# Changelog

## Unreleased

## v0.4.2 - 2026-11-25
- a fact stated in a reply or written into a file has a source that can be named, or is said to be unknown: ideas and suggestions need none

## v0.4.1 - 2026-11-21
- a change a user would notice sets the version and its changelog section itself, so the tag commands in the handover work as handed over
- a change that ships nothing to users ends with `Tag: none` and the reason, with no commands

## v0.4.0 - 2026-11-21
- a reply that edited a file and ends without a commit message and a tag is sent back once to add them
- every reply that changed a file ends with a handover, a tag that waits for a release included, and a change to the README gets a changelog line
- the README shows the image under the title and tagline

## v0.3.2 - 2026-11-21
- the README opens with the plugin's image

## v0.3.1 - 2026-11-21
- saying `stop blaming the goat` switches the rules off for the rest of the session, and the two guards stay on
- the README says what the plugin reads and runs, that it sends and stores nothing, what to do when a guard blocks and where to get help, with three example prompts
- the plugin's description names the two guards and what they block
- the plugin has an icon for a directory listing

## v0.2.0 - 2026-11-21
- the rules reach a session in full: they were cut to their first 2,000 characters once they passed 10,000
- a handover on a branch ends with a merge request subject and a description of three lines at most
- every handover suggests the next tag: a new feature raises the minor number, a fix the patch
- the version file, the tag and the changelog carry one number and change together
- a changelog is kept in every repo, per version and unreleased, unless a tool generates it
- tests go where the project keeps them, not always in `tests/`
- a suggestion is weighed in a line or two and built in the same reply
- Markdown prose keeps the wrapping the file already has, one line per paragraph in a new file
- the README has install steps for agy and codex

## v0.1.0 - 2026-10-18
- the word pass or continue in a comment or a string no longer reads as a silent skip
- only an exact yes authorizes a write, more writes are caught, and edits that cross a hard line are refused
- never a Co-Authored-By line in a commit message
- a write action runs only after a bold capital ask and a typed yes, in every permission mode
- a hook refuses commits, pushes, applies and remote writes
- the plugin installs from the Claude CLI with its skill, session hook and evals
