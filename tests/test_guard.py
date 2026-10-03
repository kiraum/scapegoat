"""The command guard refuses writes to git history, infrastructure, cloud and HTTP APIs, and lets reads through."""

from __future__ import annotations

import importlib.util
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from collections.abc import Mapping, Sequence
from pathlib import Path
from types import ModuleType

GUARD = Path(__file__).resolve().parent.parent / "hooks" / "guard.py"


def load_guard() -> ModuleType:
    """Load the guard from its file, so the tests need no install and no path setup."""
    spec = importlib.util.spec_from_file_location("guard", GUARD)
    if spec is None or spec.loader is None:
        raise ImportError(str(GUARD))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


GUARD_MODULE = load_guard()
verdict = GUARD_MODULE.verdict
denial = GUARD_MODULE.denial
tool_verdict = GUARD_MODULE.tool_verdict

BLOCKED = [
    "git commit -m x",
    "git -C ../repo commit --amend",
    "git -c user.name=x commit -m y",
    "git add -A && git commit -m x",
    "git push origin main",
    "cd repo; git push",
    "/usr/bin/git push --force",
    "git merge feature",
    "git rebase main",
    "git cherry-pick abc123",
    "git revert HEAD",
    "git pull --rebase",
    "git am patch.mbox",
    "sudo git push",
    "sudo -u deploy git push",
    "FOO=1 git commit -m x",
    "env FOO=1 git push",
    "timeout 30 git push",
    "echo abc | xargs -I{} git commit -m {}",
    'bash -c "git commit -m x"',
    'bash -lc "terraform apply"',
    "echo $(git push)",
    'echo "result: $(terraform apply -auto-approve)"',
    "bash <<'EOF'\ngit push\nEOF",
    "ls\ngit push",
    "G=/opt/homebrew/bin/git; $G add a.txt && $G commit -q -m x",
    "G=/opt/homebrew/bin/git; ${G} push",
    "export G=git; $G push",
    "TF=terraform && $TF apply -auto-approve",
    "$GIT commit -m x",
    '"$GIT_BIN" push origin main',
    "$TF apply",
    "git add -A",
    "git add -N file.py",
    "git rm old.py",
    "git tag v1.0.0",
    "git tag -d v1.0.0",
    "git reset --hard HEAD~1",
    "git reset",
    "git clean -fd",
    "git branch -D feature",
    "git branch -m old new",
    "git stash drop",
    "git stash clear",
    "git restore file.py",
    "git checkout -- file.py",
    "git checkout .",
    "npm publish",
    "pnpm publish --access public",
    "yarn publish",
    "docker push registry/app:1",
    "pulumi up",
    "pulumi destroy",
    "ansible-playbook site.yml",
    "ansible all -m shell -a reboot",
    "psql -c 'delete from users'",
    'psql "$URL" -c "UPDATE t SET a = 1"',
    "mysql -e 'drop table t'",
    "sqlite3 app.db 'insert into t values (1)'",
    "clickhouse-client --query 'ALTER TABLE t DELETE WHERE 1'",
    "rsync -a . prod:/srv/app",
    "scp build.tar.gz deploy@prod:/srv/",
    "ssh prod 'terraform apply'",
    "ssh -p 2222 deploy@prod git push",
    "docker exec app-1 git push",
    "docker compose exec app terraform apply",
    "curl -X POST https://localhost.example.com/items",
    "terraform apply",
    "terraform apply -auto-approve",
    "terraform -chdir=env/prod apply",
    "terraform destroy",
    "terraform import aws_instance.web i-123",
    "terraform state rm aws_instance.web",
    "terraform state mv a b",
    "terraform state push state.tfstate",
    "terraform taint aws_instance.web",
    "terraform untaint aws_instance.web",
    "terraform refresh",
    "terraform workspace new staging",
    "terraform workspace select prod",
    "terraform workspace delete old",
    "terraform force-unlock 1234",
    "terraform init -migrate-state",
    "terraform test",
    "tofu apply",
    "terragrunt run-all apply",
    "curl -X POST https://api.example.com/items",
    "curl -XPUT https://api.example.com/items/1",
    "curl --request PATCH https://api.example.com/items/1",
    "curl --request=DELETE https://api.example.com/items/1",
    "curl -sS -X DELETE https://api.example.com/items/1",
    "curl -d 'a=b' https://api.example.com/items",
    "curl -sd a=b https://api.example.com/items",
    "curl --data-raw '{}' https://api.example.com/items",
    "curl --json '{}' https://api.example.com/items",
    "curl -F file=@a.txt https://api.example.com/upload",
    "curl -T a.txt https://api.example.com/upload",
    "curl -s https://a.example.com | curl -X POST -d @- https://b.example.com",
    "wget --post-data=a=b https://api.example.com/items",
    "wget --method=PUT https://api.example.com/items/1",
    "wget --method DELETE https://api.example.com/items/1",
    "http POST api.example.com/items name=x",
    "http api.example.com/items name=x",
    "aws s3 cp file.txt s3://bucket/",
    "aws s3 rm s3://bucket/key",
    "aws s3 sync . s3://bucket",
    "aws ec2 terminate-instances --instance-ids i-123",
    "aws --profile prod ec2 run-instances --image-id ami-1",
    "aws ssm put-parameter --name x --value y",
    "aws lambda invoke --function-name f out.json",
    "aws logs put-retention-policy --log-group-name g --retention-in-days 1",
    "aws iam create-user --user-name x",
    "aws configure set region eu-west-1",
    "aws cloudformation deploy --template-file t.yaml --stack-name s",
    "aws autoscaling start-instance-refresh --auto-scaling-group-name g",
    "aws ec2 \\\n  terminate-instances --instance-ids i-123",
    "gcloud compute instances delete web-1",
    "gcloud config set project demo",
    "gcloud run deploy api --image img",
    "gcloud projects add-iam-policy-binding demo --member m --role r",
    "gcloud compute ssh web-1",
    "gcloud scheduler jobs run nightly",
    "gcloud auth login",
    "gsutil cp file.txt gs://bucket/",
    "gsutil rm gs://bucket/key",
    "bq query 'select 1'",
    "az vm delete -n web -g rg",
    "az group create -n rg -l westeurope",
    "az login",
    "kubectl apply -f deploy.yaml",
    "kubectl delete pod web-1",
    "kubectl -n prod scale deploy web --replicas=0",
    "kubectl exec -it web-1 -- sh",
    "kubectl rollout restart deploy/web",
    "kubectl config use-context prod",
    "helm install web ./chart",
    "helm upgrade web ./chart",
    "helm uninstall web",
    "helm repo add stable https://charts.example.com",
    "gh pr create --fill",
    "gh pr merge 12",
    "gh issue comment 3 -b done",
    "gh release create v1.0.0",
    "gh api -X POST repos/o/r/issues",
    "gh api --method PATCH repos/o/r/issues/1",
    "gh api repos/o/r/issues -f title=x",
    "gh workflow run ci.yml",
    "gh repo delete o/r --yes",
    "gh secret set TOKEN",
    "gh run rerun 99",
]

ALLOWED = [
    "git status",
    "git diff HEAD~1",
    "git log --oneline -5",
    "git log --grep commit",
    "git show HEAD",
    "git fetch origin",
    "git stash",
    "git branch -a",
    "git tag -l",
    "git commit-graph verify",
    "grep -r 'git push' docs/",
    'echo "git commit"',
    "ls # git push",
    "cat > notes.md <<'EOF'\ngit commit -m x\nterraform apply\nEOF",
    "cat <<< word\ngit status",
    "G=/opt/homebrew/bin/git; $G status --short; $G log --oneline -3",
    "PY=python3; $PY -m unittest discover -s tests",
    "$UV run pytest -q",
    "$EDITOR notes.md",
    "git tag",
    "git tag -l 'v*'",
    "git branch",
    "git branch --show-current",
    "git branch feature",
    "git stash list",
    "git stash pop",
    "git checkout main",
    "git checkout -b feature",
    "git clean -n",
    "aws s3 cp s3://bucket/key ./key",
    "aws s3 sync s3://bucket/logs ./logs",
    "aws logs start-query --log-group-name g --query-string q",
    "gcloud deploy releases list",
    "az storage blob download -c c -n n -f f",
    "kubectl port-forward svc/web 8080:80",
    "gh pr checkout 12",
    "curl -X POST localhost:8000/api/items",
    "curl -d a=b http://127.0.0.1:8000/x",
    "http POST localhost:8000/items name=x",
    "npm install",
    "docker ps",
    "docker compose logs app",
    "docker exec app-1 ls /opt/app",
    "pulumi preview",
    "pulumi stack ls",
    "ansible-playbook site.yml --check",
    "psql -c 'select 1'",
    "sqlite3 app.db 'select count(*) from t'",
    "rsync -a prod:/srv/app/logs ./logs",
    "scp deploy@prod:/srv/app.log .",
    "ssh prod 'tail -n 50 /var/log/app.log'",
    "ssh prod uptime",
    "terraform plan",
    "terraform plan -out=tf.plan",
    "terraform plan -var region=eu-west-1",
    "terraform -chdir=env/prod plan",
    "terraform validate",
    "terraform fmt -recursive",
    "terraform show",
    "terraform output -json",
    "terraform state list",
    "terraform state show aws_instance.web",
    "terraform workspace list",
    "terraform init",
    "terraform init -upgrade",
    "terraform version",
    "terraform providers",
    "tofu plan",
    "terragrunt run-all plan",
    "curl https://example.com",
    "curl -sSL https://example.com -o out.html",
    "curl -I https://example.com",
    "curl -H 'Accept: application/json' https://example.com",
    "curl -X GET https://example.com",
    "curl -G -d q=1 https://example.com/search",
    "curl -oTest.txt https://example.com",
    "curl -D headers.txt https://example.com",
    "curl -fsS localhost:8000/health",
    "wget https://example.com/file.tar.gz",
    "http GET example.com",
    "http example.com q==1",
    "aws sts get-caller-identity",
    "aws ec2 describe-instances",
    "aws --profile prod --region eu-central-1 logs filter-log-events --log-group-name /app",
    "aws s3 ls s3://bucket",
    "aws s3api get-object --bucket b --key k out.bin",
    "aws ssm get-parameter --name x --with-decryption",
    "aws logs tail /app --follow",
    "aws dynamodb scan --table-name t",
    "aws dynamodb query --table-name t",
    "aws ec2 wait instance-running --instance-ids i-123",
    "aws ec2 describe-instances --query 'Reservations[].Instances[]'",
    "aws --version",
    "aws configure list",
    "aws help",
    "gcloud compute instances list",
    "gcloud compute instances describe web-1 --zone europe-west1-b",
    "gcloud logging read 'severity>=ERROR' --limit 10 --format json",
    "gcloud config list",
    "gcloud projects get-iam-policy demo",
    "gcloud auth list",
    "gcloud run services list",
    "gcloud --version",
    "gsutil ls gs://bucket",
    "gsutil cat gs://bucket/key",
    "bq ls",
    "bq show dataset.table",
    "az account show",
    "az vm list -o table",
    "az group show -n rg",
    "kubectl get pods -A",
    "kubectl -n prod describe pod web-1",
    "kubectl logs deploy/web -f",
    "kubectl rollout status deploy/web",
    "kubectl config current-context",
    "kubectl auth can-i list pods",
    "kubectl top nodes",
    "kubectl diff -f deploy.yaml",
    "helm list -A",
    "helm status web",
    "helm template web ./chart",
    "helm repo list",
    "helm get values web",
    "gh pr list",
    "gh pr view 12 --json title",
    "gh pr diff 12",
    "gh pr checks 12",
    "gh run list",
    "gh run view 99 --log",
    "gh api repos/o/r/pulls",
    "gh api -X GET repos/o/r",
    "gh repo view",
    "gh issue list --label bug",
    "gh auth status",
    "gh search issues crash",
    "gh release download v1.0.0",
    "ls -la",
    "python3 -m pytest tests/",
    "npm test",
    "make build",
    "docker compose ps",
]


PUSH = "git push origin main"
ASK = f"**WRITE ACTION: I WILL RUN `{PUSH}`. IT PUBLISHES 2 COMMITS TO THE REMOTE. REPLY YES TO AUTHORIZE.**"


def human(text: str) -> dict[str, object]:
    """Build a transcript entry for a message the owner typed."""
    return {"type": "user", "isSidechain": False, "origin": {"kind": "human"}, "message": {"content": text}}


def assistant(text: str) -> dict[str, object]:
    """Build a transcript entry for text Claude wrote."""
    return {"type": "assistant", "isSidechain": False, "message": {"content": [{"type": "text", "text": text}]}}


def tool_use(command: str, use_id: str) -> dict[str, object]:
    """Build the transcript entry Claude leaves when it runs a shell command."""
    call = {"type": "tool_use", "id": use_id, "name": "Bash", "input": {"command": command}}
    return {"type": "assistant", "isSidechain": False, "message": {"content": [call]}}


def tool_result() -> dict[str, object]:
    """Build the transcript entry a tool result leaves, which is a user entry nobody typed."""
    return {"type": "user", "isSidechain": False, "origin": None, "message": {"content": [{"type": "tool_result"}]}}


def injected(text: str, source: str) -> dict[str, object]:
    """Build a transcript entry for a message that was not typed: a harness notification or an SDK prompt."""
    return {"type": "user", "origin": None, "promptSource": source, "message": {"content": text}}


def transcript(entries: Sequence[Mapping[str, object]]) -> str:
    """Write a session transcript to a temporary file and return its path."""
    with tempfile.NamedTemporaryFile("w", suffix=".jsonl", delete=False, encoding="utf-8") as handle:
        handle.write("\n".join(json.dumps(entry) for entry in entries) + "\n")
    return handle.name


def workspace(files: dict[str, str]) -> str:
    """Create a temporary directory holding the given files and return its path."""
    root = tempfile.mkdtemp()
    for name, content in files.items():
        target = Path(root) / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
    return root


def run_guard(payload: str) -> subprocess.CompletedProcess[str]:
    """Run the guard the way the hook does, with the event on stdin."""
    return subprocess.run([sys.executable, str(GUARD)], input=payload, capture_output=True, text=True, check=False)


def event(tool: str, command: str, transcript_path: str = "", use_id: str = "current") -> str:
    """Build the PreToolUse event Claude Code sends to a hook."""
    fields = {"hook_event_name": "PreToolUse", "tool_name": tool, "tool_input": {"command": command}}
    return json.dumps({**fields, "transcript_path": transcript_path, "tool_use_id": use_id, "cwd": os.getcwd()})


class VerdictTest(unittest.TestCase):
    """What the guard decides for a command line."""

    def test_a_write_is_flagged(self) -> None:
        """Every write gets a reason, so the hook can stop it."""
        for command in BLOCKED:
            with self.subTest(command=command):
                self.assertTrue(verdict(command))

    def test_a_read_passes(self) -> None:
        """A read-only command is not held up."""
        for command in ALLOWED:
            with self.subTest(command=command):
                self.assertIsNone(verdict(command))

    def test_the_reason_names_the_command_in_capitals(self) -> None:
        """The reason opens with WRITE ACTION, quotes the command as typed, and is otherwise upper-case."""
        reason = verdict("cd infra && terraform apply -auto-approve") or ""
        self.assertTrue(reason.startswith("WRITE ACTION: `terraform apply`"))
        self.assertTrue(re.sub(r"`[^`]*`", "", reason).isupper())


class FilesTest(unittest.TestCase):
    """The guard reads what a script, a make target, an npm script or a SQL file would run."""

    def test_a_shell_script_is_read(self) -> None:
        """A script that pushes is a write however it is started, and one that only reads is not."""
        root = workspace({"deploy.sh": "#!/bin/sh\ngit push origin main\n", "check.sh": "#!/bin/sh\ngit status\n"})
        for command in ("bash deploy.sh", "sh ./deploy.sh --fast", "./deploy.sh", "source deploy.sh", ". ./deploy.sh"):
            with self.subTest(command=command):
                self.assertTrue(verdict(command, root))
        self.assertIsNone(verdict("bash check.sh", root))
        self.assertIsNone(verdict("bash missing.sh", root))

    def test_a_cd_moves_where_the_script_is_looked_up(self) -> None:
        """The script is found relative to the directory the command line moved into."""
        root = workspace({"ops/deploy.sh": "terraform apply -auto-approve\n"})
        self.assertTrue(verdict("cd ops && bash deploy.sh", root))
        self.assertIsNone(verdict("bash deploy.sh", root))

    @unittest.skipUnless(shutil.which("make"), "make is not installed")
    def test_a_make_target_is_read(self) -> None:
        """A target whose recipe pushes is a write, and one that only builds is not."""
        root = workspace({"Makefile": "build:\n\t@echo building\n\ndeploy: build\n\tgit push origin main\n"})
        self.assertTrue(verdict("make deploy", root))
        self.assertIsNone(verdict("make build", root))

    def test_an_npm_script_is_read(self) -> None:
        """A package script is judged by the command it runs."""
        scripts = {"scripts": {"deploy": "terraform apply -auto-approve", "test": "node test.js"}}
        root = workspace({"package.json": json.dumps(scripts)})
        self.assertTrue(verdict("npm run deploy", root))
        self.assertTrue(verdict("yarn deploy", root))
        self.assertIsNone(verdict("npm run test", root))
        self.assertIsNone(verdict("npm run missing", root))

    def test_a_sql_file_is_read(self) -> None:
        """A SQL file that changes data is a write, and one that only selects is not."""
        root = workspace(
            {"purge.sql": "DELETE FROM users WHERE id = 1;\n", "report.sql": "select count(*) from users;\n"}
        )
        self.assertTrue(verdict("psql -f purge.sql", root))
        self.assertIsNone(verdict("psql -f report.sql", root))


class ConnectorTest(unittest.TestCase):
    """A connector tool that writes to an outside system is a write action too."""

    def test_a_tool_named_for_a_write_is_flagged(self) -> None:
        """The verb in the tool's name decides."""
        for tool in ("mcp__github__create_pull_request", "mcp__slack__send_message", "mcp__jira__updateIssue"):
            with self.subTest(tool=tool):
                self.assertTrue(tool_verdict(tool, {}, "."))

    def test_a_tool_named_for_a_read_passes(self) -> None:
        """Searching, reading and listing are not held up."""
        for tool in ("mcp__github__search_repositories", "mcp__memory__read_graph", "mcp__jira__getIssue"):
            with self.subTest(tool=tool):
                self.assertIsNone(tool_verdict(tool, {}, "."))


class AuthorizedTest(unittest.TestCase):
    """A write runs only when the owner's latest typed message is exactly yes, to a bold capital ask for it."""

    def test_an_exact_yes_to_the_ask_authorizes_that_command(self) -> None:
        """The plain case, with the yes written a few ways."""
        for reply in ("yes", "YES", "Yes.", "  yes  "):
            with self.subTest(reply=reply):
                path = transcript([human("push it"), assistant("Two commits are ready.\n\n" + ASK), human(reply)])
                self.assertIsNone(denial(path, "Bash", PUSH, "current"))

    def test_a_yes_with_anything_after_it_does_not_authorize(self) -> None:
        """A longer reply may be answering something else, so only the bare word counts."""
        for reply in ("yes, update the readme", "yes please", "Yes, go ahead", "no", "ok", "do whatever is needed"):
            with self.subTest(reply=reply):
                self.assertTrue(denial(transcript([assistant(ASK), human(reply)]), "Bash", PUSH, "current"))

    def test_tool_traffic_after_the_yes_does_not_cancel_it(self) -> None:
        """Tool results are user entries nobody typed, so the yes is still the latest message."""
        path = transcript([assistant(ASK), human("yes"), assistant("Running it."), tool_result()])
        self.assertIsNone(denial(path, "Bash", "git  push   origin main", "current"))

    def test_a_yes_is_spent_once_the_command_has_run(self) -> None:
        """The same command a second time needs a new ask, and the call being judged does not count against itself."""
        path = transcript([assistant(ASK), human("yes"), tool_use(PUSH, "first"), tool_result()])
        self.assertTrue(denial(path, "Bash", PUSH, "second"))
        self.assertIsNone(denial(path, "Bash", PUSH, "first"))

    def test_a_yes_covers_only_the_command_that_was_asked(self) -> None:
        """A different command needs its own ask."""
        path = transcript([assistant(ASK), human("yes")])
        self.assertTrue(denial(path, "Bash", "git push --force origin main", "current"))

    def test_the_ask_must_be_bold_and_capital(self) -> None:
        """A soft question, a lower-case ask or one without the bold markers does not count."""
        weak = [
            "Should I push to origin main?",
            f"**Write action: I will run `{PUSH}`. It publishes 2 commits. Reply yes to authorize.**",
            f"WRITE ACTION: I WILL RUN `{PUSH}`. IT PUBLISHES 2 COMMITS. REPLY YES TO AUTHORIZE.",
        ]
        for ask in weak:
            with self.subTest(ask=ask):
                self.assertTrue(denial(transcript([assistant(ask), human("yes")]), "Bash", PUSH, "current"))

    def test_names_in_the_ask_go_in_backticks(self) -> None:
        """A file or branch name keeps its case inside backticks; outside them every letter is a capital."""
        command = "git commit -am 'fix(a): b'"
        quoted = f"**WRITE ACTION: I WILL RUN `{command}`. IT COMMITS `a.txt` ON `main`. REPLY YES TO AUTHORIZE.**"
        bare = f"**WRITE ACTION: I WILL RUN `{command}`. IT COMMITS a.txt ON main. REPLY YES TO AUTHORIZE.**"
        self.assertIsNone(denial(transcript([assistant(quoted), human("yes")]), "Bash", command, "current"))
        self.assertTrue(denial(transcript([assistant(bare), human("yes")]), "Bash", command, "current"))

    def test_an_old_yes_does_not_carry_over(self) -> None:
        """Once the owner has typed something else, the earlier yes is spent."""
        path = transcript([assistant(ASK), human("yes"), assistant("Pushed."), human("now fix the readme")])
        self.assertTrue(denial(path, "Bash", PUSH, "current"))

    def test_only_a_typed_message_counts(self) -> None:
        """A yes that arrives in a harness notification, or through the SDK, is not the owner's."""
        for source in ("system", "sdk"):
            with self.subTest(source=source):
                path = transcript([human("push it"), assistant(ASK), injected("yes", source)])
                self.assertTrue(denial(path, "Bash", PUSH, "current"))

    def test_either_typed_marker_is_enough(self) -> None:
        """Claude Code marks a typed message two ways, and one of them surviving a format change is enough."""
        typed = {"type": "user", "origin": None, "promptSource": "typed", "message": {"content": "yes"}}
        self.assertIsNone(denial(transcript([assistant(ASK), typed]), "Bash", PUSH, "current"))

    def test_a_transcript_with_no_typed_message_says_so(self) -> None:
        """A headless session, or a changed transcript format, is named instead of failing without a word."""
        path = transcript([injected("push it", "sdk"), assistant(ASK), injected("yes", "sdk")])
        self.assertIn("NO TYPED MESSAGE", denial(path, "Bash", PUSH, "current") or "")

    def test_no_transcript_means_no_authorization(self) -> None:
        """Without a readable transcript nothing proves the owner said yes."""
        self.assertTrue(denial("/nonexistent/transcript.jsonl", "Bash", PUSH, "current"))


class HookTest(unittest.TestCase):
    """How the guard behaves when Claude Code runs it as a hook."""

    def test_the_hook_blocks_an_unauthorized_write_and_says_how_to_ask(self) -> None:
        """Exit code 2 blocks the call in every permission mode, and stderr gives Claude the ask to make."""
        result = run_guard(event("Bash", "git commit -m x", transcript([human("commit it")])))
        self.assertEqual(result.returncode, 2)
        self.assertTrue(result.stderr.startswith("WRITE ACTION: `git commit` WRITES HISTORY. NOT AUTHORIZED"))
        self.assertIn("**WRITE ACTION: I WILL RUN `git commit -m x`.", result.stderr)

    def test_the_hook_lets_an_authorized_write_through(self) -> None:
        """After a yes to the ask, the command goes on to the normal permission flow."""
        result = run_guard(event("Bash", PUSH, transcript([assistant(ASK), human("yes")])))
        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stdout, "")
        self.assertEqual(result.stderr, "")

    def test_the_hook_never_lets_a_co_author_trailer_through(self) -> None:
        """A commit command carrying the trailer is blocked even after a yes to that very command."""
        command = "git commit -m 'fix(a): b' -m 'Co-Authored-By: Someone <s@example.com>'"
        ask = f"**WRITE ACTION: I WILL RUN `{command}`. IT ADDS 1 COMMIT. REPLY YES TO AUTHORIZE.**"
        result = run_guard(event("Bash", command, transcript([assistant(ask), human("yes")])))
        self.assertEqual(result.returncode, 2)
        self.assertIn("`Co-Authored-By`", result.stderr)

    def test_the_hook_blocks_a_connector_write(self) -> None:
        """A connector tool is judged by its name and asked for by its name."""
        fields = {
            "hook_event_name": "PreToolUse",
            "tool_name": "mcp__github__create_issue",
            "tool_input": {"title": "x"},
        }
        result = run_guard(json.dumps({**fields, "transcript_path": transcript([human("open an issue")])}))
        self.assertEqual(result.returncode, 2)
        self.assertIn("**WRITE ACTION: I WILL RUN `mcp__github__create_issue`.", result.stderr)

    def test_the_hook_lets_a_read_through(self) -> None:
        """A read exits 0 and says nothing."""
        result = run_guard(event("Bash", "git status"))
        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stdout, "")
        self.assertEqual(result.stderr, "")

    def test_the_hook_ignores_other_tools(self) -> None:
        """Only shell commands and connector tools are judged."""
        self.assertEqual(run_guard(event("Read", "git commit -m x")).returncode, 0)

    def test_the_hook_fails_loudly_on_input_it_cannot_read(self) -> None:
        """A broken event is an error, never a silent pass."""
        result = run_guard("not json")
        self.assertNotEqual(result.returncode, 0)
        self.assertNotEqual(result.stderr, "")
