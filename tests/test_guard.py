"""The command guard refuses writes to git history, infrastructure, cloud and HTTP APIs, and lets reads through."""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
import unittest
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


verdict = load_guard().verdict

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
    "git checkout -- file.py",
    "git branch -a",
    "git tag -l",
    "git commit-graph verify",
    "grep -r 'git push' docs/",
    'echo "git commit"',
    "ls # git push",
    "cat > notes.md <<'EOF'\ngit commit -m x\nterraform apply\nEOF",
    "cat <<< word\ngit status",
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


def run_guard(payload: str) -> subprocess.CompletedProcess[str]:
    """Run the guard the way the hook does, with the event on stdin."""
    return subprocess.run([sys.executable, str(GUARD)], input=payload, capture_output=True, text=True, check=False)


def event(tool: str, command: str) -> str:
    """Build the PreToolUse event Claude Code sends to a hook."""
    return json.dumps({"hook_event_name": "PreToolUse", "tool_name": tool, "tool_input": {"command": command}})


class VerdictTest(unittest.TestCase):
    """What the guard decides for a command line."""

    def test_a_write_is_refused(self) -> None:
        """Every write gets a reason, so the hook can block it."""
        for command in BLOCKED:
            with self.subTest(command=command):
                self.assertTrue(verdict(command))

    def test_a_read_passes(self) -> None:
        """A read-only command is not held up."""
        for command in ALLOWED:
            with self.subTest(command=command):
                self.assertIsNone(verdict(command))

    def test_the_reason_names_the_command(self) -> None:
        """The refusal says which command it stopped."""
        self.assertIn("terraform apply", verdict("cd infra && terraform apply -auto-approve") or "")


class HookTest(unittest.TestCase):
    """How the guard behaves when Claude Code runs it as a hook."""

    def test_the_hook_blocks_with_exit_2_and_explains_on_stderr(self) -> None:
        """Exit code 2 is what makes Claude Code refuse the tool call."""
        result = run_guard(event("Bash", "git commit -m x"))
        self.assertEqual(result.returncode, 2)
        self.assertIn("git commit", result.stderr)

    def test_the_hook_lets_a_read_through(self) -> None:
        """A read exits 0 and says nothing."""
        result = run_guard(event("Bash", "git status"))
        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stderr, "")

    def test_the_hook_ignores_other_tools(self) -> None:
        """Only shell commands are judged."""
        self.assertEqual(run_guard(event("Read", "git commit -m x")).returncode, 0)

    def test_the_hook_fails_loudly_on_input_it_cannot_read(self) -> None:
        """A broken event is an error, never a silent pass."""
        result = run_guard("not json")
        self.assertNotIn(result.returncode, (0, 2))
        self.assertNotEqual(result.stderr, "")
