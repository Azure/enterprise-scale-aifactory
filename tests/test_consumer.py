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
from unittest import mock
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from bootstrap import consumer

EMPTY = {"schema_version": 2, "generation": "new", "factories": [],
         "configurations": {}, "bindings": {}}


class ConsumerTests(unittest.TestCase):
    def setUp(self):
        self.root = ROOT / ".consumer-test-work" / uuid4().hex
        self.root.mkdir(parents=True)
        self.source = ROOT / consumer.SUBMODULE
        subprocess.run(["git", "-C", str(self.root), "init", "-b", "consumer-branch"],
                       capture_output=True, check=True)

    def tearDown(self):
        def writable(func, path, _):
            os.chmod(path, stat.S_IWRITE)
            func(path)
        shutil.rmtree(self.root, onerror=writable)
        if not any(self.root.parent.iterdir()):
            self.root.parent.rmdir()

    def install(self, **kwargs):
        with contextlib.redirect_stdout(io.StringIO()):
            return consumer.refresh(self.root, self.source, **kwargs)

    def snapshot(self):
        return {str(p.relative_to(self.root)):
                (hashlib.sha256(p.read_bytes()).hexdigest(), p.stat().st_mtime_ns)
                if p.is_file() else None for p in self.root.rglob("*")}

    def test_dry_run_creates_nothing(self):
        before = self.snapshot()
        self.install(dry_run=True)
        self.assertEqual(before, self.snapshot())
        self.assertFalse((self.root / "azurefactory").exists())

    def test_initialize_creates_empty_register_not_legacy_bundle(self):
        self.install()
        self.assertEqual(json.loads((self.root / "azurefactory/register.json").read_text()), EMPTY)
        self.assertFalse((self.root / "aifactory").exists())
        self.assertEqual(
            {p.name for p in (self.root / ".github/workflows").iterdir()}, {"factory-lifecycle.yml"})
        self.assertEqual(
            {p.name for p in self.root.glob("*.sh")},
            {"azurefactory.sh", "AIFactory-lifecycle.sh", "ADO-azurefactory.sh", "GHA-azurefactory.sh"})
        self.assertFalse((self.root / "aifactory-templates").exists())

    def test_rerun_preserves_registered_configuration_and_blue_scripts(self):
        self.install()
        document = dict(
            EMPTY, generation="customer-owned",
            factories=[{"id": "customer", "key": "customer", "kind": "genai",
                        "scale_sets": [], "projects": []}],
            configurations={"customer": {"factory": {"version": "1.26", "custom": "kept"},
                                          "scale_sets": {}, "projects": {}, "variables": {}}},
            bindings={"customer": {"ado": {"project": "private"}}},
            ownership_evidence={"note": "customer-selected-version"})
        protected = {
            ".env": b"GITHUB_TOKEN=do-not-print\r\n",
            "02b-GH-create-or-update-github-variables.sh": b"local sync\n",
            "azurefactory/register.json": (json.dumps(document) + "\r\n").encode(),
            "azurefactory/customer-config.json": b'{"version":"do-not-change"}\r\n',
        }
        for name, value in protected.items():
            path = self.root / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(value)
        before = self.snapshot()
        self.install()
        self.assertEqual(before, self.snapshot())

    def test_existing_gitignore_bytes_preserved_with_only_api_metadata_append(self):
        original = b"# customer\r\n.env\r\n.aifactory-backups/\r\n"
        (self.root / ".gitignore").write_bytes(original)
        self.install()
        data = (self.root / ".gitignore").read_bytes()
        self.assertTrue(data.startswith(original))
        self.assertIn(b".azurefactory/\r\n", data)
        self.install()
        self.assertEqual(data, (self.root / ".gitignore").read_bytes())

    def test_all_pinned_registered_helpers_are_installed(self):
        plan = consumer.build_plan(self.root, self.source)
        self.install()
        for destination, origin in plan.items():
            self.assertTrue(destination.is_file(), str(destination))
            if destination.name != ".gitignore":
                self.assertEqual(destination.read_bytes(), origin.read_bytes())
        for relative in (
            "lib/registered_personas.py", "lib/factory_lifecycle.py",
            "lib/factory_enrollment.py", "lib/runner_bootstrap.py",
            "lib/provider_repository_state.py", "ui/terminal.sh",
            "templates/azurefactory/register.json", ".azurefactory-tools/azurefactory/cli.py",
            ".azurefactory-tools/azurefactory/_vendor/factory_enrollment.py",
            ".azurefactory-tools/azurefactory/_vendor/provider_repository_state.py",
            ".azurefactory-tools/persona-engine/personas/pipeline.py",
            ".azurefactory-tools/persona-engine/esml-util/project_lake_access.py",
        ):
            self.assertTrue((self.root / relative).is_file(), relative)

    def test_provider_selection_is_additive_without_legacy_pipelines(self):
        self.install(provider="ado")
        self.assertTrue((self.root / "ADO-azurefactory.sh").is_file())
        self.assertFalse((self.root / "GHA-azurefactory.sh").exists())
        self.assertFalse((self.root / ".github").exists())
        self.install(provider="gha", refresh_only=True)
        self.assertTrue((self.root / "ADO-azurefactory.sh").is_file())
        self.assertTrue((self.root / "GHA-azurefactory.sh").is_file())
        self.assertFalse((self.root / "aifactory").exists())
        self.assertTrue((self.root / ".github/workflows/factory-lifecycle.yml").is_file())
        self.assertFalse((self.root / "azurefactory/pipelines").exists())

    def test_scoped_github_workflow_is_exact_pinned_manual_only_template(self):
        self.install(provider="gha")
        installed = self.root / ".github/workflows/factory-lifecycle.yml"
        origin = self.source / "bootstrap/templates/factory-lifecycle-gha.yml"
        self.assertEqual(installed.read_bytes(), origin.read_bytes())
        self.assertIn(b"workflow_dispatch:", installed.read_bytes())
        self.assertNotIn(b"  push:", installed.read_bytes())
        self.assertNotIn(b"  pull_request:", installed.read_bytes())
        before = self.snapshot()
        self.install(provider="ado", refresh_only=True)
        self.assertEqual(installed.read_bytes(), origin.read_bytes())
        self.assertEqual(self.snapshot()[str(installed.relative_to(self.root))],
                         before[str(installed.relative_to(self.root))])

    def test_custom_scoped_workflow_blocks_all_writes_and_is_preserved(self):
        path = self.root / ".github/workflows/factory-lifecycle.yml"
        path.parent.mkdir(parents=True)
        path.write_bytes(b"# reviewed customer workflow\r\n")
        before = self.snapshot()
        for dry_run in (True, False):
            with self.assertRaisesRegex(ValueError, "conflict|modified|review"):
                self.install(provider="gha", dry_run=dry_run)
            self.assertEqual(before, self.snapshot())

    def test_scoped_workflow_checkout_line_endings_are_preserved(self):
        self.install(provider="gha")
        path = self.root / ".github/workflows/factory-lifecycle.yml"
        path.write_bytes(consumer.normalized(path.read_bytes()).replace(b"\n", b"\r\n"))
        before = self.snapshot()
        self.install(provider="gha")
        self.assertEqual(before, self.snapshot())

    def test_scoped_workflow_directory_conflict_is_refused_before_helper_writes(self):
        (self.root / ".github").write_bytes(b"customer-owned")
        before = self.snapshot()
        with self.assertRaisesRegex(ValueError, "directory|file"):
            self.install(provider="gha")
        self.assertEqual(before, self.snapshot())

    def test_invalid_provider_rejected_without_writes(self):
        before = self.snapshot()
        with self.assertRaisesRegex(ValueError, "provider"):
            self.install(provider="legacy")
        self.assertEqual(before, self.snapshot())

    def test_refresh_only_does_not_initialize_storage(self):
        self.install(refresh_only=True)
        self.assertFalse((self.root / "azurefactory").exists())
        self.assertTrue((self.root / "azurefactory.sh").is_file())

    def test_legacy_aifactory_refused_without_edits_or_deletion(self):
        for path in ("aifactory/variables.json", "aifactory/custom.yml"):
            target = self.root / path
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(b"customer-owned\r\n")
        before = self.snapshot()
        for dry_run in (True, False):
            with self.subTest(dry_run=dry_run):
                with self.assertRaisesRegex(ValueError, "Legacy aifactory|legacy aifactory"):
                    self.install(dry_run=dry_run)
                self.assertEqual(before, self.snapshot())

    def test_main_refuses_legacy_before_submodule_or_repair_writes(self):
        (self.root / "aifactory").mkdir()
        before = self.snapshot()
        with mock.patch.object(consumer, "ensure_submodule") as ensure, \
                mock.patch.object(consumer, "repair_submodule") as repair, \
                contextlib.redirect_stderr(io.StringIO()):
            result = consumer.main(["init", "--root", str(self.root), "--repair-submodule"])
        self.assertEqual(result, 2)
        ensure.assert_not_called()
        repair.assert_not_called()
        self.assertEqual(before, self.snapshot())

    def test_invalid_register_refused_before_any_helper_write(self):
        (self.root / "azurefactory").mkdir()
        for content in ('{}', '{"schema_version":2,"schema_version":2}', '{broken'):
            (self.root / "azurefactory/register.json").write_text(content)
            before = self.snapshot()
            with self.assertRaisesRegex(ValueError, "register|JSON"):
                self.install()
            self.assertEqual(before, self.snapshot())

    def test_nonempty_storage_without_register_is_preserved_and_refused(self):
        (self.root / "azurefactory").mkdir()
        (self.root / "azurefactory/customer.json").write_text("{}")
        before = self.snapshot()
        with self.assertRaisesRegex(ValueError, "register.json|empty"):
            self.install()
        self.assertEqual(before, self.snapshot())

    def test_custom_helper_conflict_blocks_every_write(self):
        (self.root / "azurefactory.sh").write_bytes(b"# customer helper\r\n")
        before = self.snapshot()
        for dry_run in (True, False):
            with self.assertRaisesRegex(ValueError, "conflict|modified|review"):
                self.install(dry_run=dry_run)
            self.assertEqual(before, self.snapshot())

    def test_custom_workflows_are_not_copied_over_or_removed(self):
        path = self.root / ".github/workflows/infra-common.yml"
        path.parent.mkdir(parents=True)
        path.write_bytes(b"# unrelated customer workflow\r\n")
        self.install()
        self.assertEqual(path.read_bytes(), b"# unrelated customer workflow\r\n")
        self.assertEqual({p.name for p in path.parent.iterdir()},
                         {"infra-common.yml", "factory-lifecycle.yml"})

    def test_existing_registered_config_survives_dry_run_byte_for_byte(self):
        self.install()
        (self.root / "azurefactory/register.json").write_bytes(
            (json.dumps(dict(EMPTY, generation="custom")) + "\r\n").encode())
        before = self.snapshot()
        self.install(dry_run=True)
        self.assertEqual(before, self.snapshot())

    def test_helper_checkout_line_endings_are_backed_up_before_upstream_refresh(self):
        self.install()
        path = self.root / "azurefactory.sh"
        canonical = path.read_bytes()
        original = consumer.normalized(canonical).replace(b"\n", b"\r\n")
        path.write_bytes(original)
        self.install()
        self.assertEqual(path.read_bytes(), canonical)
        if original != canonical:
            backups = list((self.root / ".aifactory-backups").glob("*/azurefactory.sh"))
            self.assertEqual(len(backups), 1)
            self.assertEqual(backups[0].read_bytes(), original)

    def test_missing_source_fails_before_writes(self):
        before = self.snapshot()
        with self.assertRaises((ValueError, FileNotFoundError)):
            consumer.refresh(self.root, self.root / "missing")
        self.assertEqual(before, self.snapshot())

    def test_nonrepository_and_nested_consumer_root_refused(self):
        nested = self.root / "nested"
        nested.mkdir()
        before = self.snapshot()
        with self.assertRaisesRegex(ValueError, "repository|root"):
            consumer.refresh(nested, self.source)
        self.assertEqual(before, self.snapshot())

    def test_hardlinked_helper_refused_without_writes(self):
        original = self.root / "customer.txt"
        original.write_text("preserve")
        os.link(original, self.root / "azurefactory.sh")
        before = self.snapshot()
        with self.assertRaisesRegex(ValueError, "[Hh]ard-linked"):
            self.install()
        self.assertEqual(before, self.snapshot())

    def test_deploy_is_diagnostic_even_with_execute_and_never_runs_commands(self):
        for arguments in ([], ["--execute", "--repo", "org/repo"], ["--dry-run"]):
            errors = io.StringIO()
            with mock.patch.object(consumer.subprocess, "run") as run, \
                    contextlib.redirect_stderr(errors):
                code = consumer.main(["deploy", *arguments])
            self.assertEqual(code, 2)
            self.assertFalse(run.called)
            self.assertIn("azurefactory.sh api instructions", errors.getvalue())
            self.assertIn("azurefactory.sh runtime deploy --help", errors.getvalue())

    def test_retired_deploy_help_succeeds_without_source_or_external_commands(self):
        output = io.StringIO()
        with mock.patch.object(consumer.subprocess, "run") as run, \
                contextlib.redirect_stdout(output):
            code = consumer.main(["deploy", "--help"])
        self.assertEqual(code, 0)
        self.assertFalse(run.called)
        self.assertIn("usage:", output.getvalue())
        self.assertIn("retired", output.getvalue())
        self.assertIn("azurefactory.sh api instructions", output.getvalue())

    def test_other_cwd_and_explicit_failure(self):
        before = self.snapshot()
        result = subprocess.run(
            [sys.executable, "-B", str(ROOT / "bootstrap/consumer.py"), "refresh",
             "--root", str(self.root), "--dry-run"], cwd=self.root,
            capture_output=True, text=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("ERROR", result.stderr)
        self.assertEqual(before, self.snapshot())

    def test_default_root_is_script_relative_from_other_cwd(self):
        before = self.snapshot()
        result = subprocess.run(
            [sys.executable, "-B", str(ROOT / "bootstrap/consumer.py"), "refresh", "--dry-run"],
            cwd=self.root, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("no files changed", result.stdout)
        self.assertEqual(before, self.snapshot())

    def test_shell_entrypoints_probe_python_runtime_and_do_not_copy_legacy_files(self):
        for name, operation in (("01b-BYORepo-init-template-files-once.sh", "init"),
                                ("03b-GH-add-aifactory-pipelines-once.sh", "refresh")):
            text = (ROOT / name).read_text(encoding="utf-8")
            self.assertIn("python3 -c 'import sys; sys.exit(sys.version_info < (3, 9))'", text)
            self.assertIn("python -c 'import sys; sys.exit(sys.version_info < (3, 9))'", text)
            self.assertIn(f'consumer.py" {operation} "$@"', text)
            self.assertNotIn("cp ", text)

    def test_checked_in_starter_is_registered_only(self):
        self.assertEqual(json.loads((ROOT / "azurefactory/register.json").read_text()), EMPTY)
        self.assertFalse((ROOT / "aifactory").exists())
        self.assertEqual(list((ROOT / ".github/workflows").glob("infra-*.yml")), [])


if __name__ == "__main__":
    unittest.main()
