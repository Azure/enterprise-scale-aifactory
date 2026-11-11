import contextlib
import io
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
    return subprocess.run(["git", "-c", "protocol.file.allow=always", "-C", str(root), *args],
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

    def test_dispatch_ref_requires_committed_selected_pin_and_templates(self):
        canonical = ROOT / consumer.SUBMODULE / consumer.SETTINGS / "github-actions"
        target = self.parent / ".github/workflows"
        target.mkdir(parents=True)
        for name in ("infra-project.yml", "infra-project-phase.yml"):
            (target / name).write_bytes(consumer.render_workflow(canonical / name))
        git(self.parent, "add", ".")
        git(self.parent, "commit", "-m", "Pinned workflow fixture")
        with mock.patch.object(consumer, "PIN", self.pin):
            consumer.validate_dispatch_ref(self.parent, ROOT / consumer.SUBMODULE, "consumer-branch", "infra-project.yml")
            with self.assertRaises(ValueError):
                consumer.validate_dispatch_ref(self.parent, ROOT / consumer.SUBMODULE, "nonexistent", "infra-project.yml")
        with self.assertRaisesRegex(ValueError, "gitlink"):
            consumer.validate_dispatch_ref(self.parent, ROOT / consumer.SUBMODULE, "consumer-branch", "infra-project.yml")

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
        ignore = shutil.ignore_patterns("*.md", "__pycache__", "*.pyc")
        for relative in (Path("bootstrap"), consumer.SETTINGS):
            shutil.copytree(source / relative, self.upstream / relative, ignore=ignore)
        variables = Path("environment_setup/aifactory/variables.json")
        shutil.copy2(source / variables, self.upstream / variables)
        for relative in consumer.ENTRY_POINTS.values():
            origin, destination = source / relative, self.upstream / relative
            if origin.is_file():
                destination.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(origin, destination)
            elif not destination.exists():
                destination.mkdir(parents=True)
                (destination / ".fixture").write_text("Interface fixture; no runtime execution.")
        git(self.upstream, "add", ".")
        git(self.upstream, "commit", "-m", "Pinned provider and bootstrap fixture")
        pin = git(self.upstream, "rev-parse", "HEAD")
        (self.upstream / "version").write_text("unselected later tip")
        git(self.upstream, "add", ".")
        git(self.upstream, "commit", "-m", "Later release fixture")

        remote = self.root / "empty-ado.git"
        git(self.root, "init", "--bare", "-b", "main", str(remote))
        target = self.root / "ado-consumer"
        git(self.root, "clone", str(remote), str(target))
        git(target, "submodule", "add", "-b", "release/v1.25", str(self.upstream), consumer.SUBMODULE)
        git(target / consumer.SUBMODULE, "checkout", "--detach", pin)
        git(target, "add", "--", ".gitmodules", consumer.SUBMODULE)

        (target / "bootstrap").mkdir()
        helper = (ROOT / "bootstrap/consumer.py").read_text(encoding="utf-8")
        # Only the disposable fixture's expected Git object differs from production.
        helper = helper.replace(f'PIN = "{consumer.PIN}"', f'PIN = "{pin}"', 1)
        (target / "bootstrap/consumer.py").write_text(helper, encoding="utf-8")
        script = "01b-BYORepo-init-template-files-once.sh"
        shutil.copy2(ROOT / script, target / script)
        shutil.copy2(ROOT / ".gitignore", target / ".gitignore")
        (target / ".env").write_text("CUSTOMER_VALUE=preserve\n")
        bash = shutil.which("bash")
        if os.name == "nt":
            git_bash = Path(os.environ.get("ProgramFiles", r"C:\Program Files")) / "Git/bin/bash.exe"
            if git_bash.is_file():
                bash = str(git_bash)
        self.assertIsNotNone(bash, "Git Bash is a test prerequisite.")
        for args in (["--dry-run"], []):
            result = subprocess.run([bash, str(target / script), *args], cwd=self.root,
                                    capture_output=True, text=True, timeout=90)
            self.assertEqual(result.returncode, 0, result.stderr)
            if args:
                self.assertFalse((target / "aifactory").exists())
        config = target / "aifactory/variables.json"
        config.write_text('{"dev":{"customer":"preserved"}}\n')
        result = subprocess.run([bash, str(target / script)], cwd=self.root,
                                capture_output=True, text=True, timeout=90)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(config.read_text(), '{"dev":{"customer":"preserved"}}\n')
        self.assertEqual((target / ".env").read_text(), "CUSTOMER_VALUE=preserve\n")
        self.assertTrue((target / consumer.ADO / "esml-infra-project/infra-project-genai.yaml").is_file())
        self.assertTrue((target / "lib/bootstrap_no_delete.py").is_file())
        self.assertEqual(git(target / consumer.SUBMODULE, "rev-parse", "HEAD"), pin)
        self.assertEqual(git(target / consumer.SUBMODULE, "status", "--porcelain"), "")


if __name__ == "__main__":
    unittest.main()
