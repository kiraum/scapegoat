#!/usr/bin/env python3
"""PreToolUse guard: blocks a write to git, infra, an API or a connector unless the owner said yes to an ask for it."""

from __future__ import annotations

import itertools
import json
import os
import re
import shlex
import shutil
import subprocess
import sys
from typing import Any, Callable, Optional

Check = Callable[[list[str]], Optional[str]]
FileCheck = Callable[[list[str], str, int], Optional[str]]

MAX_DEPTH = 3
MAX_FILE_BYTES = 200_000
MAKE_SECONDS = 3

SHELLS = {"bash", "sh", "zsh", "dash", "ksh"}
SOURCING = {"source", "."}
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
SHELL_SHEBANG = re.compile(r"#!.*\b(sh|bash|zsh|dash|ksh)\b")
VARIABLE = re.compile(r"\$\{?([A-Za-z_][A-Za-z0-9_]*)\}?")
DECLARATIONS = {"export", "local", "declare", "readonly", "typeset"}

ASK = re.compile(r"\*\*WRITE ACTION: I WILL RUN `([^`]+)`(?:`[^`]*`|[^a-z*`])*REPLY YES TO AUTHORIZE\.\*\*")
YES = re.compile(r"\s*yes[.!]?\s*", re.I)
TRAILER = re.compile(r"co-authored-by", re.I)

GIT_VALUE_OPTS = frozenset({"-C", "-c", "--git-dir", "--work-tree", "--namespace"})
GIT_HISTORY = {"commit", "commit-tree", "push", "merge", "rebase", "cherry-pick", "revert", "am", "pull"}
GIT_WRITES = {
    **{sub: "writes history" for sub in GIT_HISTORY},
    **{sub: "changes the index" for sub in ("add", "rm", "mv")},
    **{sub: "discards work" for sub in ("reset", "restore")},
}
GIT_TAG_WRITE_OPTS = {"-d", "--delete", "-a", "--annotate", "-s", "--sign", "-f", "--force", "-m", "-F"}
GIT_BRANCH_WRITE_OPTS = {"-d", "-D", "--delete", "-m", "-M", "--move", "-c", "-C", "--copy", "-f", "--force"}
GIT_CHECKOUT_DISCARDS = {"--", ".", "-f", "--force"}
DRY_RUN_CLUSTER = re.compile(r"-[A-Za-z]*n[A-Za-z]*")

UNMISTAKABLE_WRITES = GIT_HISTORY | {"apply", "destroy", "import"}

TF_READS = {"plan", "validate", "fmt", "show", "output", "providers", "version", "graph", "init", "get", "metadata"}
TF_NESTED_READS = {"state": {"list", "show", "pull"}, "workspace": {"list", "show"}}
TF_INIT_WRITES = ("migrate-state", "force-copy")
TERRAGRUNT_PREFIXES = {"run-all", "run"}

CURL_VALUE_LETTERS = set("XdFTHoubAecmwxKEDCrYyzPQtU")
CURL_BODY_LETTERS = {"d", "F", "T"}
CURL_BODY_OPTS = ("--data", "--json", "--form", "--upload-file")
WGET_BODY_OPTS = ("--post-data", "--post-file", "--body-data", "--body-file")
HTTPIE_DATA = re.compile(r"[\w.\-\[\]]+(:=|=)(?!=).*", re.S)
URLISH = re.compile(r"[a-z][a-z0-9+.-]*://|localhost\b|127\.0\.0\.1|0\.0\.0\.0|\[::1\]", re.I)
LOOPBACK = re.compile(
    r"(?:[a-z][a-z0-9+.-]*://)?(?:localhost|127\.0\.0\.1|0\.0\.0\.0|\[::1\])(?::\d+)?(?:[/?#].*)?", re.I
)

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
AWS_EXTRA_READS = {("logs", "start-query"), ("logs", "stop-query")}
AWS_S3_COPIES = {"cp", "sync"}

VERB_WRITE = re.compile(
    r"(create|delete|update|set|unset|add|remove|deploy|apply|patch|import|start|stop|restart|reset|resize|enable"
    r"|disable|attach|detach|promote|rollback|submit|ssh|scp|cp|mv|rm|rsync|replace|edit|scale|login|logout|activate"
    r"|revoke|move|rename|restore|purge|invoke|execute|call|cancel|kill|terminate|reboot|migrate|failover|upgrade"
    r"|install|uninstall|push|publish|rotate|undelete|abandon|suspend|resume|clear|drain)(-.+)?"
)
VERB_READ = re.compile(
    r"(list|describe|show|get|read|tail|info|version|help|lookup|search|query|history|status|print|view|download"
    r"|export)(-.+)?"
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
    "port-forward",
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
PULUMI_READS = {"preview", "version", "whoami", "about", "help", "logs"}
PULUMI_NESTED_READS = {"stack": {"", "ls", "output", "history", "graph"}, "config": {"", "get"}}
ANSIBLE_PLAYBOOK_READS = {"--check", "-C", "--syntax-check", "--list-hosts", "--list-tasks", "--list-tags", "--version"}
ANSIBLE_READS = {"--list-hosts", "--version"}

GH_VALUE_OPTS = frozenset({"-R", "--repo", "--hostname"})
GH_GROUP_READS = {"status", "search", "help", "version", "completion"}
GH_VERB_READS = {"list", "view", "status", "diff", "checks", "watch", "download", "clone", "get", "check", "checkout"}
GH_FIELD_OPTS = ("-f", "-F", "--field", "--raw-field", "--input")

DOCKER_VALUE_OPTS = frozenset(
    {"-H", "--host", "--context", "--config", "-l", "--log-level", "-f", "--file", "-p", "--project-name", "--profile"}
)
DOCKER_EXEC_VALUE_OPTS = frozenset({"-u", "--user", "-e", "--env", "-w", "--workdir", "--env-file", "--detach-keys"})
SSH_VALUE_OPTS = frozenset(set("-" + letter for letter in "pilJoFLRDbcemSWwEBIQ"))
REMOTE_PATH = re.compile(r"[^/\s:]+:.*|rsync://.*")
SQL_WRITE = re.compile(
    r"\b(insert|update|delete|drop|alter|truncate|create|grant|revoke|replace|merge|upsert|rename|optimize)\b", re.I
)
PACKAGE_RUN = {"run", "run-script"}

CONNECTOR_WORD = re.compile(r"[A-Za-z][a-z0-9]*")
CONNECTOR_WRITES = {
    "create",
    "update",
    "delete",
    "remove",
    "send",
    "post",
    "put",
    "patch",
    "write",
    "edit",
    "merge",
    "close",
    "reopen",
    "comment",
    "reply",
    "add",
    "set",
    "upload",
    "publish",
    "move",
    "rename",
    "archive",
    "assign",
    "approve",
    "cancel",
    "trigger",
    "execute",
    "invite",
    "share",
    "insert",
    "upsert",
    "append",
    "replace",
    "submit",
    "deploy",
    "push",
    "commit",
}


def write_action(what: str, why: str) -> str:
    """Word the reason the same way for every tool: capitals, with the command as typed."""
    return f"WRITE ACTION: `{what}` {why.upper()}."


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
    """Return the value given to an option, written as name=value or as name followed by the value."""
    for index, word in enumerate(args):
        if word == name:
            return args[index + 1] if index + 1 < len(args) else ""
        if word.startswith(name + "="):
            return word.split("=", 1)[1]
    return ""


def inner_command(rest: list[str], value_opts: frozenset[str]) -> list[str]:
    """Return the command handed to ssh or docker exec, after their own options and the host or container."""
    index = 0
    while index < len(rest) and rest[index].startswith("-"):
        index += 2 if rest[index] in value_opts else 1
    return rest[index + 1 :]


def read_text(name: str, cwd: str) -> Optional[str]:
    """Return a small file's text, or None when it is not there or is too large to judge."""
    path = os.path.join(cwd, name)
    if not os.path.isfile(path) or os.path.getsize(path) > MAX_FILE_BYTES:
        return None
    with open(path, encoding="utf-8", errors="replace") as handle:
        return handle.read()


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


def only_loopback(args: list[str]) -> bool:
    """Tell whether a command names at least one address and every one of them is this machine."""
    targets = [word for word in args if not word.startswith("-") and URLISH.match(word)]
    return bool(targets) and all(LOOPBACK.fullmatch(word) for word in targets)


def git_detail(sub: str, rest: list[str]) -> Optional[str]:
    """Return what a git subcommand writes, judged with its own options, or None when it only reads."""
    plain = [word for word in rest if not word.startswith("-")]
    if sub == "tag":
        listing = "-l" in rest or "--list" in rest or not (plain or GIT_TAG_WRITE_OPTS.intersection(rest))
        return None if listing else "writes a ref"
    if sub == "branch":
        return "deletes or moves a branch" if GIT_BRANCH_WRITE_OPTS.intersection(rest) else None
    if sub == "stash":
        return "discards work" if plain[:1] in (["drop"], ["clear"]) else None
    if sub == "checkout":
        return "discards work" if GIT_CHECKOUT_DISCARDS.intersection(rest) else None
    if sub == "clean":
        dry_run = "--dry-run" in rest or any(DRY_RUN_CLUSTER.fullmatch(word) for word in rest)
        return None if dry_run else "discards work"
    return GIT_WRITES.get(sub)


def check_git(args: list[str]) -> Optional[str]:
    """Flag the git commands that write history, change the index or discard work."""
    sub = (positionals(args, GIT_VALUE_OPTS) or [""])[0]
    why = git_detail(sub, args[args.index(sub) + 1 :]) if sub else None
    return write_action(f"git {sub}", why) if why else None


def nested_check(
    tool: str,
    reads: set[str],
    nested_reads: dict[str, set[str]],
    value_opts: frozenset[str] = frozenset(),
    why: str = "is not a read-only command",
) -> Check:
    """Build a check for a CLI with subcommands: only the listed read-only ones pass."""

    def check(args: list[str]) -> Optional[str]:
        """Flag a subcommand that is not on the read-only list."""
        words = positionals(args, value_opts)
        if not words:
            return None
        sub = words[0]
        nested = words[1] if len(words) > 1 else ""
        if sub in nested_reads:
            return None if nested in nested_reads[sub] else write_action(f"{tool} {sub} {nested}".strip(), why)
        return None if sub in reads else write_action(f"{tool} {sub}", why)

    return check


def check_terraform(args: list[str]) -> Optional[str]:
    """Flag every terraform command that can change infrastructure or state."""
    words = [word for word in args if word not in TERRAGRUNT_PREFIXES]
    migrates = [word for word in words if word.lstrip("-").startswith(TF_INIT_WRITES)]
    if "init" in positionals(words)[:1] and migrates:
        return write_action(f"terraform init {migrates[0]}", "moves state")
    return nested_check("terraform", TF_READS, TF_NESTED_READS, why="changes infrastructure or state")(words)


def check_curl(args: list[str]) -> Optional[str]:
    """Flag curl when it sends a write method or a request body to anything but this machine."""
    method = request_method(args, "--request")
    options = [short_option(word) for word in args]
    uploads = [word for word, (_, letter, _) in zip(args, options) if letter in CURL_BODY_LETTERS]
    uploads += [word for word in args if word.startswith(CURL_BODY_OPTS)]
    as_query = "--get" in args or any("G" in plain for plain, _, _ in options)
    only_data = all(word.startswith(("-d", "--data")) or "d" in short_option(word)[1] for word in uploads)
    if only_loopback(args):
        return None
    if method in WRITE_METHODS:
        return write_action(f"curl -X {method}", "writes to an HTTP API")
    if uploads and not (method in READ_METHODS or (as_query and only_data)):
        return write_action(f"curl {uploads[0]}", "sends a request body, which writes to an HTTP API")
    return None


def check_wget(args: list[str]) -> Optional[str]:
    """Flag wget when it sends a write method or a request body to anything but this machine."""
    method = option_value(args, "--method").upper()
    bodies = [word for word in args if word.startswith(WGET_BODY_OPTS)]
    if (method in WRITE_METHODS or bodies) and not only_loopback(args):
        return write_action(f"wget {(bodies or ['--method=' + method])[0]}", "writes to an HTTP API")
    return None


def check_httpie(args: list[str]) -> Optional[str]:
    """Flag httpie when it names a write method or carries data items, unless it talks to this machine."""
    words = positionals(args)
    method = words[0].upper() if words else ""
    data = [word for word in words if HTTPIE_DATA.fullmatch(word)]
    writes = method in WRITE_METHODS or (data and method not in READ_METHODS)
    if writes and not only_loopback(words):
        return write_action(f"http {method or data[0]}", "writes to an HTTP API")
    return None


def check_aws(args: list[str]) -> Optional[str]:
    """Flag every aws operation that is not a read; an s3 copy is a read when it lands on this machine."""
    words = positionals(args, AWS_VALUE_OPTS)
    if len(words) < 2:
        return None
    service, operation = words[0], words[1]
    if service == "s3" and operation in AWS_S3_COPIES:
        allowed = len(words) > 3 and words[2].startswith("s3://") and not words[3].startswith("s3://")
    elif service in AWS_SERVICE_READS:
        allowed = operation in AWS_SERVICE_READS[service]
    else:
        allowed = (service, operation) in AWS_EXTRA_READS or bool(AWS_READ.fullmatch(operation))
    return None if allowed else write_action(f"aws {service} {operation}", "is not a read-only call")


def verb_check(tool: str) -> Check:
    """Build a check for a CLI whose commands end in a verb, such as gcloud or az."""

    def check(args: list[str]) -> Optional[str]:
        """Flag a command that names a write verb, or no read verb at all, leaving its first word as the group."""
        named = strict_positionals(args)
        words = [word for word in args if not word.startswith("-")]
        group = named[:1] if len(named) > 1 else []
        verbs = [word for word in named if word not in group]
        writes = [word for word in words if word not in group and VERB_WRITE.fullmatch(word)]
        reads = [word for word in verbs if VERB_READ.fullmatch(word)]
        if writes or (verbs and not reads):
            return write_action(f"{tool} {' '.join(named[:4])}".strip(), "is not a read-only command")
        return None

    return check


def check_gh(args: list[str]) -> Optional[str]:
    """Flag every gh command that changes something on GitHub."""
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
    return None if allowed else write_action(f"gh {group} {verb}".strip(), "is not a read-only command")


def flag_check(tool: str, reads: set[str], why: str) -> Check:
    """Build a check for a tool that writes unless one of the listed read-only flags is given."""

    def check(args: list[str]) -> Optional[str]:
        """Flag the command when none of the read-only flags is present."""
        return None if reads.intersection(args) else write_action(tool, why)

    return check


def check_remote_copy(tool: str) -> Check:
    """Build a check for rsync or scp: a copy is a write when it lands on another host."""

    def check(args: list[str]) -> Optional[str]:
        """Flag a copy whose destination, the last word, is a remote path."""
        destination = args[-1] if args and not args[-1].startswith("-") else ""
        remote = REMOTE_PATH.fullmatch(destination)
        return write_action(f"{tool} {destination}", "writes to another host") if remote else None

    return check


def args_only(check: Check) -> FileCheck:
    """Adapt a check that needs only the arguments to the signature every check is called with."""

    def adapted(args: list[str], _cwd: str, _depth: int) -> Optional[str]:
        """Run the check on the arguments alone."""
        return check(args)

    return adapted


def check_script(args: list[str], cwd: str, depth: int) -> Optional[str]:
    """Flag a shell script whose own commands include a write action."""
    name = (positionals(args) or [""])[0]
    content = read_text(name, cwd) if name else None
    return verdict(content, cwd, depth + 1) if content else None


def check_program_file(path: str, cwd: str, depth: int) -> Optional[str]:
    """Flag a shell script started by its path, such as ./deploy.sh."""
    content = read_text(path, cwd)
    is_shell = bool(content) and (path.endswith(".sh") or bool(SHELL_SHEBANG.match(content or "")))
    return verdict(content or "", cwd, depth + 1) if is_shell else None


def check_make(args: list[str], cwd: str, depth: int) -> Optional[str]:
    """Flag a make target whose recipe, as a dry run prints it, includes a write action."""
    if not shutil.which("make") or not os.path.isdir(cwd):
        return None
    try:
        dry = subprocess.run(
            ["make", "-n", *args], cwd=cwd, capture_output=True, text=True, timeout=MAKE_SECONDS, check=False
        )
    except subprocess.TimeoutExpired:
        return write_action(
            f"make {' '.join(args)}".strip(), "could not be read in time, so it is not known to be safe"
        )
    return verdict(dry.stdout, cwd, depth + 1) if dry.returncode == 0 else None


def package_check(tool: str) -> FileCheck:
    """Build a check for npm, yarn or pnpm: publishing is a write, and a script is judged by what it runs."""

    def check(args: list[str], cwd: str, depth: int) -> Optional[str]:
        """Flag a publish, or a package script whose command is a write action."""
        words = positionals(args)
        if words[:1] == ["publish"]:
            return write_action(f"{tool} publish", "publishes a package")
        name = words[1] if words[:1] and words[0] in PACKAGE_RUN and len(words) > 1 else (words or [""])[0]
        manifest = read_text("package.json", cwd)
        script = json.loads(manifest).get("scripts", {}).get(name) if manifest else None
        return verdict(script, cwd, depth + 1) if script else None

    return check


def check_docker(args: list[str], cwd: str, depth: int) -> Optional[str]:
    """Flag a docker push, and judge the command a docker exec runs inside a container."""
    words = positionals(args, DOCKER_VALUE_OPTS)
    lead = words[1:2] if words[:1] == ["compose"] else words[:1]
    if lead == ["push"]:
        return write_action("docker push", "publishes an image")
    inner = inner_command(args[args.index("exec") + 1 :], DOCKER_EXEC_VALUE_OPTS) if lead == ["exec"] else []
    return check_segment(inner, cwd, depth + 1) if inner else None


def check_ssh(args: list[str], cwd: str, depth: int) -> Optional[str]:
    """Judge the command ssh runs on the remote host."""
    remote = inner_command(args, SSH_VALUE_OPTS)
    return verdict(" ".join(remote), cwd, depth + 1) if remote else None


def sql_check(tool: str) -> FileCheck:
    """Build a check for a SQL client: a statement that changes data or schema is a write."""

    def check(args: list[str], cwd: str, _depth: int) -> Optional[str]:
        """Flag SQL given on the command line or in a file when it changes data or schema."""
        files = [option_value(args, "-f"), option_value(args, "--file")]
        texts = [word for word in args if not word.startswith("-")]
        texts += [read_text(name, cwd) or "" for name in files if name]
        changes = any(SQL_WRITE.search(text) for text in texts)
        return write_action(tool, "runs SQL that changes data or schema") if changes else None

    return check


CHECKS: dict[str, FileCheck] = {
    "git": args_only(check_git),
    "terraform": args_only(check_terraform),
    "tofu": args_only(check_terraform),
    "terragrunt": args_only(check_terraform),
    "curl": args_only(check_curl),
    "wget": args_only(check_wget),
    "http": args_only(check_httpie),
    "https": args_only(check_httpie),
    "xh": args_only(check_httpie),
    "aws": args_only(check_aws),
    "gcloud": args_only(verb_check("gcloud")),
    "az": args_only(verb_check("az")),
    "gsutil": args_only(nested_check("gsutil", GSUTIL_READS, {}, GSUTIL_VALUE_OPTS)),
    "bq": args_only(nested_check("bq", BQ_READS, {})),
    "kubectl": args_only(nested_check("kubectl", KUBECTL_READS, KUBECTL_NESTED_READS, KUBECTL_VALUE_OPTS)),
    "oc": args_only(nested_check("oc", KUBECTL_READS, KUBECTL_NESTED_READS, KUBECTL_VALUE_OPTS)),
    "helm": args_only(nested_check("helm", HELM_READS, HELM_NESTED_READS, HELM_VALUE_OPTS)),
    "pulumi": args_only(nested_check("pulumi", PULUMI_READS, PULUMI_NESTED_READS)),
    "ansible-playbook": args_only(
        flag_check("ansible-playbook", ANSIBLE_PLAYBOOK_READS, "changes the hosts it targets")
    ),
    "ansible": args_only(flag_check("ansible", ANSIBLE_READS, "runs a module on the hosts it targets")),
    "gh": args_only(check_gh),
    "rsync": args_only(check_remote_copy("rsync")),
    "scp": args_only(check_remote_copy("scp")),
    "npm": package_check("npm"),
    "yarn": package_check("yarn"),
    "pnpm": package_check("pnpm"),
    "docker": check_docker,
    "ssh": check_ssh,
    "make": check_make,
    "gmake": check_make,
    "psql": sql_check("psql"),
    "mysql": sql_check("mysql"),
    "mariadb": sql_check("mariadb"),
    "sqlite3": sql_check("sqlite3"),
    "clickhouse-client": sql_check("clickhouse-client"),
    "source": check_script,
    ".": check_script,
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


def check_unresolved(program: str, args: list[str]) -> Optional[str]:
    """Flag a program held in a variable the guard cannot resolve, when its subcommand is an unmistakable write."""
    sub = (positionals(args) or [""])[0]
    return write_action(f"{program} {sub}", "runs a write through a variable") if sub in UNMISTAKABLE_WRITES else None


def assignments(words: list[str]) -> dict[str, str]:
    """Return the variables a command sets with leading NAME=value words, with or without export."""
    named = words[1:] if words and words[0] in DECLARATIONS else words
    leading = itertools.takewhile(ASSIGNMENT.fullmatch, named)
    return {name: value for name, _, value in (word.partition("=") for word in leading)}


def expand(words: list[str], known: dict[str, str]) -> list[str]:
    """Replace the variables set earlier on the same command line with their values."""
    return [VARIABLE.sub(lambda match: known.get(match.group(1), match.group(0)), word) for word in words]


def check_segment(words: list[str], cwd: str, depth: int) -> Optional[str]:
    """Return why one simple command is a write action, or None when it is read-only."""
    command = unwrap(words)
    if not command:
        return None
    program, args = os.path.basename(command[0]), command[1:]
    if program.startswith("$"):
        return check_unresolved(program, args)
    if program in SHELLS:
        script = shell_script(args)
        return verdict(script, cwd, depth + 1) if script is not None else check_script(args, cwd, depth)
    if program == "eval":
        return verdict(" ".join(args), cwd, depth + 1)
    if program in CHECKS:
        return CHECKS[program](args, cwd, depth)
    return check_program_file(command[0], cwd, depth) if "/" in command[0] or program.endswith(".sh") else None


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


def verdict(command: str, cwd: str = ".", depth: int = 0) -> Optional[str]:
    """Return why a shell line is a write action, or None when every command in it is read-only."""
    if depth > MAX_DEPTH:
        return None
    text = strip_heredocs(command.replace("\\\n", " "))
    known: dict[str, str] = {}
    reasons: list[Optional[str]] = []
    here = cwd
    for segment in split_segments(text.replace("\n", " ; ")):
        words = expand(segment, known)
        known.update(assignments(words))
        reasons.append(check_segment(words, here, depth))
        if words[0] == "cd" and len(words) > 1:
            here = os.path.normpath(os.path.join(here, words[1]))
    reasons += [verdict(inner or quoted, cwd, depth + 1) for inner, quoted in SUBSTITUTION.findall(text)]
    return next((reason for reason in reasons if reason), None)


def check_connector(tool: str) -> Optional[str]:
    """Flag a connector tool whose name carries a write verb, such as create, update, delete or send."""
    words = {word.lower() for word in CONNECTOR_WORD.findall(tool.split("__")[-1])}
    return write_action(tool, "writes through a connector") if words & CONNECTOR_WRITES else None


def tool_verdict(tool: str, tool_input: dict[str, Any], cwd: str) -> Optional[str]:
    """Return why a tool call is a write action, or None: shell commands and connector tools are judged."""
    if tool == "Bash":
        command = tool_input.get("command", "")
        return verdict(command, cwd) if command else None
    return check_connector(tool) if tool.startswith("mcp__") else None


def one_line(command: str) -> str:
    """Collapse a command to one line with single spaces, the form it has in an ask."""
    return " ".join(command.split())


def entry_text(entry: dict[str, Any]) -> str:
    """Return the text a transcript entry carries, leaving out tool calls and tool results."""
    content = entry.get("message", {}).get("content", "")
    if isinstance(content, str):
        return content
    return "\n".join(part.get("text", "") for part in content if isinstance(part, dict) and part.get("type") == "text")


def is_typed(entry: dict[str, Any]) -> bool:
    """Tell whether the owner typed this message, by either of the two marks Claude Code leaves on it."""
    marked = (entry.get("origin") or {}).get("kind") == "human" or entry.get("promptSource") == "typed"
    return entry.get("type") == "user" and marked


def earlier_runs(entries: list[dict[str, Any]], tool: str, tool_use_id: str) -> list[str]:
    """Return the commands this tool already ran in these entries, leaving out the call being judged."""
    parts = [
        part
        for entry in entries
        if entry.get("type") == "assistant" and isinstance(entry.get("message", {}).get("content"), list)
        for part in entry["message"]["content"]
        if isinstance(part, dict) and part.get("type") == "tool_use" and part.get("id") != tool_use_id
    ]
    ran = [part for part in parts if part.get("name") == tool]
    return [one_line(part.get("input", {}).get("command", "") if tool == "Bash" else tool) for part in ran]


def read_transcript(path: str) -> list[dict[str, Any]]:
    """Return the main conversation's entries, or none when the transcript cannot be read."""
    try:
        with open(path, encoding="utf-8") as handle:
            lines = handle.read().splitlines()
    except OSError as error:
        print(f"scapegoat guard: no transcript to check for a yes: {error}", file=sys.stderr)
        return []
    entries = [json.loads(line) for line in lines if line.strip()]
    return [entry for entry in entries if not entry.get("isSidechain")]


def denial(transcript_path: str, tool: str, command: str, tool_use_id: str) -> Optional[str]:
    """Return why the owner has not authorized this call, or None when their latest typed message is a yes to it."""
    entries = read_transcript(transcript_path)
    typed = [index for index, entry in enumerate(entries) if is_typed(entry)]
    if not typed:
        return "NO TYPED MESSAGE IN THE TRANSCRIPT: A HEADLESS SESSION CANNOT AUTHORIZE, OR ITS FORMAT CHANGED"
    if not YES.fullmatch(entry_text(entries[typed[-1]])):
        return "THE OWNER'S LAST MESSAGE IS NOT EXACTLY YES"
    turn_start = typed[-2] + 1 if len(typed) > 1 else 0
    said = "\n".join(entry_text(entry) for entry in entries[turn_start : typed[-1]] if entry.get("type") == "assistant")
    if one_line(command) not in [one_line(asked) for asked in ASK.findall(said)]:
        return "NO ASK FOR THIS EXACT COMMAND CAME BEFORE THE YES"
    if one_line(command) in earlier_runs(entries[typed[-1] + 1 :], tool, tool_use_id):
        return "THAT YES WAS ALREADY USED ONCE"
    return None


def blocked(reason: str, command: str, why: str) -> str:
    """Word the block for Claude: what was stopped, why, and the exact ask that would authorize it."""
    ask = (
        f"**WRITE ACTION: I WILL RUN `{one_line(command)}`. IT <WHAT IT CHANGES, AND WHERE>. REPLY YES TO AUTHORIZE.**"
    )
    how = "ASK THE OWNER FIRST, AS THE LAST LINE OF YOUR REPLY, THEN STOP"
    form = "NAMES GO IN BACKTICKS, EVERY OTHER LETTER IS A CAPITAL. ONLY A REPLY THAT IS EXACTLY YES COUNTS."
    return f"{reason} NOT AUTHORIZED: {why}. {how}: {ask} {form}"


def main() -> int:
    """Read the PreToolUse event from stdin and block a write the owner has not said yes to."""
    event = json.load(sys.stdin)
    tool = event.get("tool_name", "")
    tool_input = event.get("tool_input", {})
    reason = tool_verdict(tool, tool_input, event.get("cwd") or ".")
    if not reason:
        return 0
    command = tool_input.get("command", "") if tool == "Bash" else tool
    if tool == "Bash" and TRAILER.search(command) and reason.startswith("WRITE ACTION: `git"):
        trailer = "WRITE ACTION: `git commit` CARRIES A `Co-Authored-By` LINE."
        print(f"{trailer} A COMMIT MESSAGE IS ONE LINE WITH NO TRAILER: REMOVE IT AND ASK AGAIN.", file=sys.stderr)
        return 2
    why = denial(event.get("transcript_path", ""), tool, command, event.get("tool_use_id", ""))
    if why:
        print(blocked(reason, command, why), file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
