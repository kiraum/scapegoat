#!/usr/bin/env python3
"""PreToolUse guard for Bash: refuses commands that write to git history, infrastructure, cloud or HTTP APIs."""

from __future__ import annotations

import json
import os
import re
import shlex
import sys
from typing import Callable, Optional

Check = Callable[[list[str]], Optional[str]]

SHELLS = {"bash", "sh", "zsh", "dash", "ksh"}
WRAPPER_VALUE_OPTS: dict[str, set[str]] = {
    "sudo": {"-u", "-g", "-h", "-p", "-C", "-D", "-R", "-T", "-U"},
    "doas": {"-u", "-C"},
    "env": {"-u", "-C"},
    "nice": {"-n"},
    "timeout": {"-s", "-k"},
    "xargs": {"-I", "-n", "-P", "-L", "-d", "-s", "-E", "-a"},
    "command": set(),
    "exec": set(),
    "nohup": set(),
    "time": set(),
    "builtin": set(),
    "noglob": set(),
}
WRITE_METHODS = {"POST", "PUT", "PATCH", "DELETE"}
READ_METHODS = {"GET", "HEAD", "OPTIONS"}

ASSIGNMENT = re.compile(r"[A-Za-z_][A-Za-z0-9_]*=.*", re.S)
DURATION = re.compile(r"\d+(\.\d+)?[smhd]?")
SEPARATOR = re.compile(r"[();|&]+")
LOOSE_WORD = re.compile(r"[();|&]+|[^\s();|&]+")
HEREDOC = re.compile(r"(?<!<)<<(?!<)-?\s*(['\"]?)([A-Za-z_][A-Za-z0-9_]*)\1")
SUBSTITUTION = re.compile(r"\$\(([^()]*)\)|`([^`]*)`")
SHELL_SCRIPT_FLAG = re.compile(r"-[A-Za-z]*c")

GIT_VALUE_OPTS = frozenset({"-C", "-c", "--git-dir", "--work-tree", "--namespace"})
GIT_WRITES = {"commit", "commit-tree", "push", "merge", "rebase", "cherry-pick", "revert", "am", "pull"}

TF_READS = {"plan", "validate", "fmt", "show", "output", "providers", "version", "graph", "init", "get", "metadata"}
TF_NESTED_READS = {"state": {"list", "show", "pull"}, "workspace": {"list", "show"}}
TF_INIT_WRITES = ("migrate-state", "force-copy")
TERRAGRUNT_PREFIXES = {"run-all", "run"}

CURL_VALUE_LETTERS = set("XdFTHoubAecmwxKEDCrYyzPQtU")
CURL_BODY_LETTERS = {"d", "F", "T"}
CURL_BODY_OPTS = ("--data", "--json", "--form", "--upload-file")
WGET_BODY_OPTS = ("--post-data", "--post-file", "--body-data", "--body-file")
HTTPIE_DATA = re.compile(r"[\w.\-\[\]]+(:=|=)(?!=).*", re.S)

AWS_VALUE_OPTS = frozenset(
    {
        "--profile",
        "--region",
        "--output",
        "--endpoint-url",
        "--query",
        "--color",
        "--ca-bundle",
        "--cli-read-timeout",
        "--cli-connect-timeout",
        "--cli-binary-format",
    }
)
AWS_READ = re.compile(
    r"(describe|list|get|head|lookup|search|filter|batch-get|select|simulate|estimate|check|validate|preview|decode)-.+"
    r"|ls|query|scan|tail|help|wait|presign"
)
AWS_SERVICE_READS = {"s3": {"ls", "presign"}, "configure": {"list", "list-profiles", "get"}}

VERB_WRITE = re.compile(
    r"(create|delete|update|set|unset|add|remove|deploy|apply|patch|import|start|stop|restart|reset|resize|enable"
    r"|disable|attach|detach|promote|rollback|submit|ssh|scp|cp|mv|rm|rsync|replace|edit|scale|login|logout|activate"
    r"|revoke|move|rename|restore|purge|invoke|execute|call|cancel|kill|terminate|reboot|migrate|failover|upgrade"
    r"|install|uninstall|push|publish|rotate|undelete|abandon|suspend|resume|clear|drain)(-.+)?"
)
VERB_READ = re.compile(
    r"(list|describe|show|get|read|tail|info|version|help|lookup|search|query|history|status|print|view)(-.+)?"
)

KUBECTL_VALUE_OPTS = frozenset(
    {"-n", "--namespace", "--context", "--kubeconfig", "--cluster", "--user", "-s", "--server", "--as"}
)
KUBECTL_READS = {
    "get",
    "describe",
    "logs",
    "top",
    "explain",
    "version",
    "api-resources",
    "api-versions",
    "cluster-info",
    "events",
    "diff",
    "wait",
    "kustomize",
    "help",
}
KUBECTL_NESTED_READS = {
    "auth": {"can-i", "whoami"},
    "config": {"view", "get-contexts", "current-context", "get-clusters", "get-users"},
    "rollout": {"status", "history"},
}
HELM_VALUE_OPTS = frozenset({"-n", "--namespace", "--kube-context", "--kubeconfig"})
HELM_READS = {
    "list",
    "ls",
    "status",
    "get",
    "history",
    "show",
    "search",
    "template",
    "lint",
    "version",
    "env",
    "help",
    "verify",
    "diff",
}
HELM_NESTED_READS = {"repo": {"list"}, "dependency": {"list"}, "plugin": {"list"}}
GSUTIL_VALUE_OPTS = frozenset({"-o", "-h", "-i", "-u"})
GSUTIL_READS = {"ls", "cat", "stat", "du", "version", "help", "hash"}
BQ_READS = {"ls", "show", "head", "version", "help"}

GH_VALUE_OPTS = frozenset({"-R", "--repo", "--hostname"})
GH_GROUP_READS = {"status", "search", "help", "version", "completion"}
GH_VERB_READS = {"list", "view", "status", "diff", "checks", "watch", "download", "clone", "get", "check"}
GH_FIELD_OPTS = ("-f", "-F", "--field", "--raw-field", "--input")


def refusal(what: str, why: str) -> str:
    """Word a refusal the same way for every tool."""
    return f"scapegoat guard: `{what}` {why}. Hand the command to the owner instead of running it."


def positionals(args: list[str], value_opts: frozenset[str] = frozenset()) -> list[str]:
    """Return the words that are not options, skipping the value of each listed option."""
    found: list[str] = []
    index = 0
    while index < len(args):
        word = args[index]
        if word in value_opts:
            index += 2
        elif word.startswith("-"):
            index += 1
        else:
            found.append(word)
            index += 1
    return found


def strict_positionals(args: list[str]) -> list[str]:
    """Return the words that are neither options nor the word right after an option written without '='."""
    found: list[str] = []
    after_option = False
    for word in args:
        is_option = word.startswith("-")
        if not is_option and not after_option:
            found.append(word)
        after_option = is_option and "=" not in word
    return found


def option_value(args: list[str], name: str) -> str:
    """Return the value given to a long option, written as name=value or as name followed by the value."""
    for index, word in enumerate(args):
        if word == name:
            return args[index + 1] if index + 1 < len(args) else ""
        if word.startswith(name + "="):
            return word.split("=", 1)[1]
    return ""


def short_option(word: str) -> tuple[str, str, str]:
    """Split a short-option cluster into its plain letters, its first value-taking letter and the text glued to it."""
    if word.startswith("--") or not word.startswith("-"):
        return "", "", ""
    for position, letter in enumerate(word[1:], start=1):
        if letter in CURL_VALUE_LETTERS:
            return word[1:position], letter, word[position + 1 :]
    return word[1:], "", ""


def request_method(args: list[str], long_name: str) -> str:
    """Return the HTTP method a command was told to use, upper-cased, or an empty string."""
    for index, word in enumerate(args):
        _, letter, glued = short_option(word)
        if letter == "X":
            following = args[index + 1] if index + 1 < len(args) else ""
            return (glued or following).strip().upper()
    return option_value(args, long_name).strip().upper()


def check_git(args: list[str]) -> Optional[str]:
    """Refuse the git commands that write a commit or publish one."""
    sub = (positionals(args, GIT_VALUE_OPTS) or [""])[0]
    return refusal(f"git {sub}", "writes history, which the owner does") if sub in GIT_WRITES else None


def nested_check(
    tool: str,
    reads: set[str],
    nested_reads: dict[str, set[str]],
    value_opts: frozenset[str] = frozenset(),
    why: str = "is not a read-only command",
) -> Check:
    """Build a check for a CLI with subcommands: only the listed read-only ones pass."""

    def check(args: list[str]) -> Optional[str]:
        """Refuse a subcommand that is not on the read-only list."""
        words = positionals(args, value_opts)
        if not words:
            return None
        sub = words[0]
        nested = words[1] if len(words) > 1 else ""
        if sub in nested_reads:
            return None if nested in nested_reads[sub] else refusal(f"{tool} {sub} {nested}".strip(), why)
        return None if sub in reads else refusal(f"{tool} {sub}", why)

    return check


def check_terraform(args: list[str]) -> Optional[str]:
    """Refuse every terraform command that can change infrastructure or state."""
    words = [word for word in args if word not in TERRAGRUNT_PREFIXES]
    migrates = [word for word in words if word.lstrip("-").startswith(TF_INIT_WRITES)]
    if "init" in positionals(words)[:1] and migrates:
        return refusal(f"terraform init {migrates[0]}", "moves state")
    return nested_check("terraform", TF_READS, TF_NESTED_READS, why="changes infrastructure or state")(words)


def check_curl(args: list[str]) -> Optional[str]:
    """Refuse curl when it sends a write method or a request body."""
    method = request_method(args, "--request")
    options = [short_option(word) for word in args]
    uploads = [word for word, (_, letter, _) in zip(args, options) if letter in CURL_BODY_LETTERS]
    uploads += [word for word in args if word.startswith(CURL_BODY_OPTS)]
    as_query = "--get" in args or any("G" in plain for plain, _, _ in options)
    only_data = all(word.startswith(("-d", "--data")) or "d" in short_option(word)[1] for word in uploads)
    if method in WRITE_METHODS:
        return refusal(f"curl -X {method}", "writes to an HTTP API")
    if uploads and not (method in READ_METHODS or (as_query and only_data)):
        return refusal(f"curl {uploads[0]}", "sends a request body, which writes to an HTTP API")
    return None


def check_wget(args: list[str]) -> Optional[str]:
    """Refuse wget when it sends a write method or a request body."""
    method = option_value(args, "--method").upper()
    bodies = [word for word in args if word.startswith(WGET_BODY_OPTS)]
    if method in WRITE_METHODS or bodies:
        return refusal(f"wget {(bodies or ['--method=' + method])[0]}", "writes to an HTTP API")
    return None


def check_httpie(args: list[str]) -> Optional[str]:
    """Refuse httpie when it names a write method or carries data items, which make it POST."""
    words = positionals(args)
    method = words[0].upper() if words else ""
    data = [word for word in words if HTTPIE_DATA.fullmatch(word)]
    if method in WRITE_METHODS or (data and method not in READ_METHODS):
        return refusal(f"http {method or data[0]}", "writes to an HTTP API")
    return None


def check_aws(args: list[str]) -> Optional[str]:
    """Refuse every aws operation that is not a read."""
    words = positionals(args, AWS_VALUE_OPTS)
    if len(words) < 2:
        return None
    service, operation = words[0], words[1]
    if service in AWS_SERVICE_READS:
        allowed = operation in AWS_SERVICE_READS[service]
    else:
        allowed = bool(AWS_READ.fullmatch(operation))
    return None if allowed else refusal(f"aws {service} {operation}", "is not a read-only call")


def verb_check(tool: str) -> Check:
    """Build a check for a CLI whose commands end in a verb, such as gcloud or az."""

    def check(args: list[str]) -> Optional[str]:
        """Refuse a command that names a write verb, or no read verb at all."""
        named = strict_positionals(args)
        writes = [word for word in args if not word.startswith("-") and VERB_WRITE.fullmatch(word)]
        reads = [word for word in named if VERB_READ.fullmatch(word)]
        if writes or (named and not reads):
            return refusal(f"{tool} {' '.join(named[:4])}".strip(), "is not a read-only command")
        return None

    return check


def check_gh(args: list[str]) -> Optional[str]:
    """Refuse every gh command that changes something on GitHub."""
    words = positionals(args, GH_VALUE_OPTS)
    if not words:
        return None
    group = words[0]
    verb = words[1] if len(words) > 1 else ""
    if group == "api":
        method = request_method(args, "--method")
        fields = [word for word in args if word.startswith(GH_FIELD_OPTS)]
        allowed = method not in WRITE_METHODS and (not fields or method in READ_METHODS)
    elif group == "auth":
        allowed = verb == "status"
    else:
        allowed = group in GH_GROUP_READS or verb in GH_VERB_READS
    return None if allowed else refusal(f"gh {group} {verb}".strip(), "is not a read-only command")


CHECKS: dict[str, Check] = {
    "git": check_git,
    "terraform": check_terraform,
    "tofu": check_terraform,
    "terragrunt": check_terraform,
    "curl": check_curl,
    "wget": check_wget,
    "http": check_httpie,
    "https": check_httpie,
    "xh": check_httpie,
    "aws": check_aws,
    "gcloud": verb_check("gcloud"),
    "az": verb_check("az"),
    "gsutil": nested_check("gsutil", GSUTIL_READS, {}, GSUTIL_VALUE_OPTS),
    "bq": nested_check("bq", BQ_READS, {}),
    "kubectl": nested_check("kubectl", KUBECTL_READS, KUBECTL_NESTED_READS, KUBECTL_VALUE_OPTS),
    "oc": nested_check("oc", KUBECTL_READS, KUBECTL_NESTED_READS, KUBECTL_VALUE_OPTS),
    "helm": nested_check("helm", HELM_READS, HELM_NESTED_READS, HELM_VALUE_OPTS),
    "gh": check_gh,
}


def drop_wrapper_options(wrapper: str, rest: list[str]) -> list[str]:
    """Drop a wrapper's own options, and their values, from the front of its arguments."""
    value_opts = WRAPPER_VALUE_OPTS[wrapper]
    index = 0
    while index < len(rest) and rest[index].startswith("-"):
        index += 2 if rest[index] in value_opts else 1
    if wrapper == "timeout" and index < len(rest) and DURATION.fullmatch(rest[index]):
        index += 1
    return rest[index:]


def unwrap(words: list[str]) -> list[str]:
    """Strip leading variable assignments and wrapper programs such as sudo, env, timeout or xargs."""
    rest = list(words)
    while rest and (ASSIGNMENT.fullmatch(rest[0]) or os.path.basename(rest[0]) in WRAPPER_VALUE_OPTS):
        head = os.path.basename(rest[0])
        rest = drop_wrapper_options(head, rest[1:]) if head in WRAPPER_VALUE_OPTS else rest[1:]
    return rest


def shell_script(args: list[str]) -> Optional[str]:
    """Return the script a shell was given with -c, if any."""
    flags = [index for index, word in enumerate(args) if SHELL_SCRIPT_FLAG.fullmatch(word)]
    return args[flags[0] + 1] if flags and flags[0] + 1 < len(args) else None


def check_segment(words: list[str]) -> Optional[str]:
    """Return why one simple command is refused, or None when it is read-only."""
    command = unwrap(words)
    if not command:
        return None
    program, args = os.path.basename(command[0]), command[1:]
    script = shell_script(args) if program in SHELLS else None
    if script is not None:
        return verdict(script)
    if program == "eval":
        return verdict(" ".join(args))
    check = CHECKS.get(program)
    return check(args) if check else None


def feeds_shell(prefix: str) -> bool:
    """Tell whether the text before a heredoc operator runs a shell, which would execute the body."""
    words = re.split(r"[|;&]+", prefix)[-1].split()
    return bool(words) and os.path.basename(words[0]) in SHELLS


def strip_heredocs(command: str) -> str:
    """Drop heredoc bodies, which are data, unless the heredoc feeds a shell."""
    kept: list[str] = []
    terminator: Optional[str] = None
    for line in command.split("\n"):
        if terminator is None:
            kept.append(line)
            match = HEREDOC.search(line)
            if match and not feeds_shell(line[: match.start()]):
                terminator = match.group(2)
        elif line.strip() == terminator:
            terminator = None
    return "\n".join(kept)


def split_segments(command: str) -> list[list[str]]:
    """Split a shell line into its simple commands, each a list of words."""
    lexer = shlex.shlex(command, posix=True, punctuation_chars=True)
    lexer.whitespace_split = True
    lexer.commenters = ""
    try:
        tokens = list(lexer)
    except ValueError:
        # Unbalanced quotes: split on plain words instead, so the command is still judged.
        tokens = LOOSE_WORD.findall(command)
    segments: list[list[str]] = [[]]
    for token in tokens:
        if SEPARATOR.fullmatch(token):
            segments.append([])
        else:
            segments[-1].append(token)
    return [segment for segment in segments if segment]


def verdict(command: str) -> Optional[str]:
    """Return why a shell line is refused, or None when every command in it is read-only."""
    text = strip_heredocs(command.replace("\\\n", " "))
    reasons = [check_segment(segment) for segment in split_segments(text.replace("\n", " ; "))]
    reasons += [verdict(inner or quoted) for inner, quoted in SUBSTITUTION.findall(text)]
    return next((reason for reason in reasons if reason), None)


def main() -> int:
    """Read the PreToolUse event from stdin and refuse a Bash command that writes."""
    event = json.load(sys.stdin)
    command = event.get("tool_input", {}).get("command", "") if event.get("tool_name") == "Bash" else ""
    reason = verdict(command) if command else None
    if reason:
        print(reason, file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
