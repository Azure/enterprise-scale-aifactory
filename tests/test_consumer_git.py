import contextlib
import hashlib
import io
import json
import os
from pathlib import Path
import shutil
import stat
import subprocess
import sys
import unittest
from uuid import uuid4
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from bootstrap import consumer


def git(root, *args):
    env = {**os.environ, "GIT_AUTHOR_NAME": "Consumer Test",
           "GIT_AUTHOR_EMAIL": "test@example.invalid", "GIT_COMMITTER_NAME": "Consumer Test",
           "GIT_COMMITTER_EMAIL": "test@example.invalid", "GIT_CONFIG_NOSYSTEM": "1"}
    return subprocess.run(["git", "-c", "protocol.file.allow=always", "-c", "core.longpaths=true",
                           "-C", str(root), *args],
                          env=env, check=True, capture_output=True, text=True).stdout.strip()


class ConsumerGitTests(unittest.TestCase):
    def setUp(self):
        self.root = ROOT / ".consumer-test-work" / uuid4().hex
        self.root.mkdir(parents=True)
        self.upstream = self.root / "upstream"
        self.upstream.mkdir()
        git(self.upstream, "init", "-b", "release/v1.25")
        (self.upstream / "version").write_text("pinned")
        git(self.upstream, "add", ".")
        git(self.upstream, "commit", "-m", "Pinned fixture")
        self.pin = git(self.upstream, "rev-parse", "HEAD")
        self.parent = self.root / "parent"
        self.parent.mkdir()
        git(self.parent, "init", "-b", "consumer-branch")
        git(self.parent, "submodule", "add", str(self.upstream), consumer.SUBMODULE)
        git(self.parent, "add", ".")
        git(self.parent, "commit", "-m", "Consumer fixture")
        (self.upstream / "version").write_text("later-unselected")
        git(self.upstream, "add", ".")
        git(self.upstream, "commit", "-m", "Later branch tip")

    def tearDown(self):
        def writable(func, path, _):
            os.chmod(path, stat.S_IWRITE)
            func(path)
        shutil.rmtree(self.root, onerror=writable)
        if not any(self.root.parent.iterdir()):
            self.root.parent.rmdir()

    def test_local_init_and_rerun_use_gitlink_not_branch_tip(self):
        clone = self.root / "clone"
        git(self.root, "clone", "--no-local", str(self.parent), str(clone))
        old = os.environ.get("GIT_ALLOW_PROTOCOL")
        os.environ["GIT_ALLOW_PROTOCOL"] = "file"
        try:
            consumer.ensure_submodule(clone, expected=self.pin)
            consumer.ensure_submodule(clone, expected=self.pin)
        finally:
            if old is None:
                os.environ.pop("GIT_ALLOW_PROTOCOL", None)
            else:
                os.environ["GIT_ALLOW_PROTOCOL"] = old
        self.assertEqual(git(clone / consumer.SUBMODULE, "rev-parse", "HEAD"), self.pin)
        self.assertEqual((clone / consumer.SUBMODULE / "version").read_text(), "pinned")
        self.assertEqual(git(clone, "branch", "--show-current"), "consumer-branch")

    def test_recursive_clone_matches_selected_gitlink(self):
        clone = self.root / "recursive"
        git(self.root, "clone", "--recurse-submodules", str(self.parent), str(clone))
        consumer.ensure_submodule(clone, expected=self.pin)
        self.assertEqual(git(clone / consumer.SUBMODULE, "rev-parse", "HEAD"), self.pin)

    def test_dry_run_does_not_initialize(self):
        clone = self.root / "dry"
        git(self.root, "clone", str(self.parent), str(clone))
        with contextlib.redirect_stdout(io.StringIO()):
            consumer.ensure_submodule(clone, expected=self.pin, dry_run=True)
        self.assertFalse((clone / consumer.SUBMODULE / ".git").exists())

    def test_wrong_gitlink_fails_without_checkout(self):
        with self.assertRaisesRegex(ValueError, "gitlink|pin"):
            consumer.ensure_submodule(self.parent, expected="0" * 40)
        self.assertEqual(git(self.parent / consumer.SUBMODULE, "rev-parse", "HEAD"), self.pin)

    def test_dirty_source_fails_without_mutating_it(self):
        (self.parent / consumer.SUBMODULE / "version").write_text("user-change")
        with self.assertRaisesRegex(ValueError, "dirty|modified"):
            consumer.ensure_submodule(self.parent, expected=self.pin)
        self.assertEqual((self.parent / consumer.SUBMODULE / "version").read_text(), "user-change")

    def test_local_checkout_ahead_of_gitlink_is_not_reset(self):
        git(self.parent / consumer.SUBMODULE, "fetch", "origin")
        git(self.parent / consumer.SUBMODULE, "checkout", "origin/release/v1.25")
        newer = git(self.parent / consumer.SUBMODULE, "rev-parse", "HEAD")
        with self.assertRaisesRegex(ValueError, "differs.*pin"):
            consumer.ensure_submodule(self.parent, expected=self.pin)
        self.assertEqual(git(self.parent / consumer.SUBMODULE, "rev-parse", "HEAD"), newer)

    def test_dirty_source_dry_run_fails_without_mutating_source_or_consumer(self):
        source = self.parent / consumer.SUBMODULE
        (source / "customer.txt").write_text("preserve")
        status = git(self.parent, "status", "--porcelain")
        with self.assertRaisesRegex(ValueError, "dirty|modified"):
            consumer.ensure_submodule(self.parent, expected=self.pin, dry_run=True)
        self.assertEqual((source / "customer.txt").read_text(), "preserve")
        self.assertEqual(git(self.parent, "status", "--porcelain"), status)

    def test_populated_uninitialized_submodule_is_not_deleted_or_adopted(self):
        clone = self.root / "populated"
        git(self.root, "clone", str(self.parent), str(clone))
        source = clone / consumer.SUBMODULE
        (source / "customer.txt").write_text("preserve")
        with self.assertRaisesRegex(ValueError, "populated|metadata"):
            consumer.ensure_submodule(clone, expected=self.pin)
        self.assertEqual((source / "customer.txt").read_text(), "preserve")
        self.assertFalse((source / ".git").exists())

    def test_explicit_repair_initializes_exact_pin_without_branch_tip(self):
        repaired = self.root / "repaired"
        repaired.mkdir()
        git(repaired, "init", "-b", "consumer-branch")
        consumer.repair_submodule(repaired, expected=self.pin, url=str(self.upstream))
        with mock.patch.dict(os.environ, {"GIT_ALLOW_PROTOCOL": "file"}):
            consumer.ensure_submodule(repaired, expected=self.pin)
        self.assertEqual(git(repaired / consumer.SUBMODULE, "rev-parse", "HEAD"), self.pin)
        self.assertEqual(git(repaired, "config", "--file", ".gitmodules", "--get",
                             f"submodule.{consumer.SUBMODULE}.branch"), "release/v1.25")
        self.assertIn(self.pin, git(repaired, "ls-files", "--stage", "--", consumer.SUBMODULE))
        consumer.repair_submodule(repaired, expected=self.pin, url=str(self.upstream))

    def test_repair_dry_run_does_not_create_metadata_or_stage_gitlink(self):
        repaired = self.root / "repair-dry"
        repaired.mkdir()
        git(repaired, "init", "-b", "consumer-branch")
        consumer.repair_submodule(repaired, expected=self.pin, url=str(self.upstream), dry_run=True)
        self.assertFalse((repaired / ".gitmodules").exists())
        self.assertFalse((repaired / consumer.SUBMODULE).exists())
        self.assertEqual(git(repaired, "ls-files"), "")

    def test_repair_refuses_populated_untracked_path(self):
        repaired = self.root / "repair-populated"
        repaired.mkdir()
        git(repaired, "init", "-b", "consumer-branch")
        path = repaired / consumer.SUBMODULE
        path.mkdir()
        (path / "customer.txt").write_text("preserve")
        with self.assertRaisesRegex(ValueError, "populated|untracked"):
            consumer.repair_submodule(repaired, expected=self.pin, url=str(self.upstream))
        self.assertEqual((path / "customer.txt").read_text(), "preserve")
        self.assertFalse((repaired / ".gitmodules").exists())
        self.assertEqual(git(repaired, "ls-files"), "")

    def test_missing_gitmodules_requires_explicit_repair(self):
        (self.parent / ".gitmodules").unlink()
        with self.assertRaisesRegex(ValueError, "repair-submodule"):
            consumer.ensure_submodule(self.parent, expected=self.pin)
        consumer.repair_submodule(self.parent, expected=self.pin, url=str(self.upstream))
        consumer.ensure_submodule(self.parent, expected=self.pin)
        self.assertEqual(git(self.parent / consumer.SUBMODULE, "rev-parse", "HEAD"), self.pin)

    def test_empty_ado_recipe_runs_copied_blue_initializer_and_preserves_rerun(self):
        source = ROOT / consumer.SUBMODULE
        remote = self.root / "empty-ado.git"
        git(self.root, "init", "--bare", "-b", "main", str(remote))
        target = self.root / "ado-consumer"
        git(self.root, "clone", str(remote), str(target))
        selected = target / consumer.SUBMODULE
        # A local sparse checkout exercises the exact immutable object without a
        # network fetch or projecting unrelated (very long) example paths.
        git(target, "clone", "--shared", "--no-checkout", str(source), str(selected))
        git(selected, "config", "core.longpaths", "true")
        git(selected, "sparse-checkout", "set", "bootstrap", "environment_setup/azurefactory-cli",
            "environment_setup/aifactory/bicep/personas", "environment_setup/aifactory/bicep/esml-util")
        git(selected, "checkout", "--detach", consumer.PIN)
        git(target, "submodule", "add", str(source), consumer.SUBMODULE)
        git(target, "config", "--file", ".gitmodules", f"submodule.{consumer.SUBMODULE}.branch", consumer.BRANCH)
        git(target, "add", "--", ".gitmodules", consumer.SUBMODULE)

        (target / "bootstrap").mkdir()
        shutil.copy2(ROOT / "bootstrap/consumer.py", target / "bootstrap/consumer.py")
        script = "01b-BYORepo-init-template-files-once.sh"
        shutil.copy2(ROOT / script, target / script)
        shutil.copy2(ROOT / ".gitignore", target / ".gitignore")
        shutil.copy2(ROOT / ".gitattributes", target / ".gitattributes")
        (target / ".env").write_text("CUSTOMER_VALUE=preserve\n")
        bash = shutil.which("bash")
        if os.name == "nt":
            git_bash = Path(os.environ.get("ProgramFiles", r"C:\Program Files")) / "Git/bin/bash.exe"
            if git_bash.is_file():
                bash = str(git_bash)
        self.assertIsNotNone(bash, "Git Bash is a test prerequisite.")
        def snapshot():
            return {str(p.relative_to(target)): (hashlib.sha256(p.read_bytes()).hexdigest(),
                                                 p.stat().st_mtime_ns) if p.is_file() else None
                    for p in target.rglob("*")}

        before = snapshot()
        for args in (["--dry-run", "--provider", "ado"], ["--provider", "ado"]):
            result = subprocess.run([bash, str(target / script), *args], cwd=self.root,
                                    capture_output=True, text=True, timeout=90)
            self.assertEqual(result.returncode, 0, result.stderr)
            if "--dry-run" in args:
                self.assertEqual(before, snapshot())
                self.assertFalse((target / "azurefactory").exists())
        config = target / "azurefactory/register.json"
        document = json.loads(config.read_text())
        document["ownership_evidence"] = {"customer": "preserved"}
        config.write_bytes((json.dumps(document) + "\r\n").encode())
        before = snapshot()
        result = subprocess.run([bash, str(target / script), "--provider", "ado"], cwd=self.root,
                                capture_output=True, text=True, timeout=90)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(before, snapshot())
        self.assertEqual((target / ".env").read_text(), "CUSTOMER_VALUE=preserve\n")
        self.assertTrue((target / "ADO-azurefactory.sh").is_file())
        self.assertFalse((target / "GHA-azurefactory.sh").exists())
        self.assertFalse((target / "aifactory").exists())
        self.assertFalse((target / ".github/workflows").exists())
        self.assertEqual({p.name for p in target.glob("*.sh")},
                         {script, "azurefactory.sh", "AIFactory-lifecycle.sh", "ADO-azurefactory.sh"})
        self.assertTrue((target / "lib/bootstrap_no_delete.py").is_file())
        self.assertTrue((target / ".azurefactory-tools/azurefactory/cli.py").is_file())
        self.assertTrue((target / ".azurefactory-tools/persona-engine/personas/pipeline.py").is_file())
        refresh_script = "03b-GH-add-aifactory-pipelines-once.sh"
        shutil.copy2(ROOT / refresh_script, target / refresh_script)
        register_bytes = config.read_bytes()
        result = subprocess.run([bash, str(target / refresh_script), "--provider", "gha"],
                                cwd=self.root, capture_output=True, text=True, timeout=90)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue((target / "GHA-azurefactory.sh").is_file())
        self.assertTrue((target / "ADO-azurefactory.sh").is_file())
        self.assertEqual(config.read_bytes(), register_bytes)
        self.assertFalse((target / "aifactory").exists())
        scoped_workflow = target / ".github/workflows/factory-lifecycle.yml"
        self.assertEqual(scoped_workflow.read_bytes(),
                         (selected / "bootstrap/templates/factory-lifecycle-gha.yml").read_bytes())
        self.assertEqual({p.name for p in scoped_workflow.parent.iterdir()}, {"factory-lifecycle.yml"})
        self.assertFalse((target / "azurefactory/pipelines").exists())
        deploy_script = "04ab-setup-infra-aifactory.sh"
        shutil.copy2(ROOT / deploy_script, target / deploy_script)
        before = snapshot()
        result = subprocess.run(
            [bash, str(target / deploy_script), "--execute", "--repo", "org/repo"],
            cwd=self.root, capture_output=True, text=True, timeout=90)
        self.assertEqual(result.returncode, 2)
        self.assertIn("azurefactory.sh runtime deploy --help", result.stderr)
        self.assertEqual(before, snapshot())
        result = subprocess.run(
            [bash, str(target / script), "--repair-submodule", "--dry-run", "--provider", "ado"],
            cwd=self.root, capture_output=True, text=True, timeout=90)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("Registered plan", result.stdout)
        self.assertEqual(before, snapshot())
        for arguments in (["--help"], ["factory", "create", "--help"], ["runtime", "deploy", "--help"],
                          ["api", "instructions"]):
            result = subprocess.run([bash, str(target / "azurefactory.sh"), *arguments],
                                    cwd=self.root, capture_output=True, text=True, timeout=90)
            self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(git(target / consumer.SUBMODULE, "rev-parse", "HEAD"), consumer.PIN)
        self.assertEqual(git(target / consumer.SUBMODULE, "status", "--porcelain"), "")


if __name__ == "__main__":
    unittest.main()
