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


class ConsumerTests(unittest.TestCase):
    def setUp(self):
        self.root = ROOT / ".consumer-test-work" / uuid4().hex
        self.root.mkdir(parents=True)
        self.source = ROOT / consumer.SUBMODULE

    def tearDown(self):
        def writable(func, path, _):
            os.chmod(path, stat.S_IWRITE)
            func(path)
        shutil.rmtree(self.root, onerror=writable)
        if not any(self.root.parent.iterdir()):
            self.root.parent.rmdir()

    def install(self, dry_run=False):
        with contextlib.redirect_stdout(io.StringIO()):
            return consumer.refresh(self.root, self.source, dry_run=dry_run)

    def snapshot(self):
        return {str(p.relative_to(self.root)): hashlib.sha256(p.read_bytes()).hexdigest()
                for p in self.root.rglob("*") if p.is_file()}

    def test_dry_run_creates_nothing(self):
        self.install(dry_run=True)
        self.assertEqual(list(self.root.iterdir()), [])

    def test_initialize_and_rerun_preserve_active_configuration_and_sync_script(self):
        self.install()
        protected = {
            ".env": "GITHUB_TOKEN=do-not-print\n",
            ".gitignore": "# local\n",
            "02b-GH-create-or-update-github-variables.sh": "local sync\n",
            "aifactory/variables.json": '{"dev":{"enableFactoryChatAgent":"true","custom":"kept"}}\n',
            "aifactory/esml-infra/azure-devops/bicep/yaml/variables/variables.yaml":
                'variables:\n  custom: "kept"\n',
        }
        for name, value in protected.items():
            path = self.root / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(value, encoding="utf-8")
        before = self.snapshot()
        self.install()
        self.assertEqual(before, self.snapshot())
        for name, value in protected.items():
            self.assertEqual((self.root / name).read_text(encoding="utf-8"), value)

    def test_current_workflows_and_complete_helpers_available(self):
        self.install()
        for name in consumer.WORKFLOWS:
            target = self.root / ".github" / "workflows" / name
            origin = self.source / consumer.SETTINGS / "github-actions" / name
            self.assertEqual(target.read_bytes(), consumer.render_workflow(origin))
        for name in ("lib/bootstrap_no_delete.py", "lib/initialize_azurefactory.py",
                     "lib/registered_personas.py", "ui/terminal.sh",
                     "templates/azurefactory/register.json"):
            self.assertTrue((self.root / name).is_file(), name)
        for old in ("infra-project-esml.yml", "infra-project-genai.yml",
                    "infra-add-core-member.yml", "infra-add-project-member.yml"):
            self.assertFalse((self.root / ".github/workflows" / old).exists())
        self.assertFalse((self.root / "azurefactory").exists())

    def test_new_config_metadata_and_optional_services(self):
        self.install()
        config = json.loads((self.root / "aifactory/variables.json").read_text())
        original = json.loads((self.source / "environment_setup/aifactory/variables.json").read_text())
        for section in config.values():
            if not isinstance(section, dict):
                continue
            if "aifactory_branch_chosen" in section:
                self.assertEqual(section["aifactory_branch_chosen"], "release/v1.25")
                self.assertEqual(section["aifactory_version_minor"], "25")
        for flag in ("enableFactoryChatAgent", "enableAIFactoryAgentLiveVoice",
                     "enableAIGatewaySKU", "ENABLE_APIM", "ENABLE_KONG", "enableAppInsightsDashboard"):
            self.assertEqual(config["dev"][flag], original["dev"][flag], flag)
            self.assertIn(config["dev"][flag], (False, "false"), flag)

    def test_registered_layout_rejected_without_writes(self):
        (self.root / "azurefactory").mkdir()
        (self.root / "azurefactory/register.json").write_text("{}")
        before = self.snapshot()
        with self.assertRaisesRegex(ValueError, "registered|azurefactory"):
            self.install()
        self.assertEqual(before, self.snapshot())

    def test_missing_source_fails_before_writes(self):
        with self.assertRaises((ValueError, FileNotFoundError)):
            consumer.refresh(self.root, self.root / "missing")
        self.assertEqual(list(self.root.iterdir()), [])

    def test_upstream_public_entry_points_and_provider_templates_exist(self):
        for name, relative in consumer.ENTRY_POINTS.items():
            self.assertTrue((self.source / relative).exists(), name)
        self.install()
        for relative in (
            "esml-infra-common/infra-ai-gateway.yaml",
            "esml-infra-project/infra-project-genai.yaml",
            "esml-infra-project/infra-project-dashboards.yaml",
            "esml-infra-project/infra-project-healthmodel.yaml",
            "esml-infra-project/infra-project-azure-mcp.yaml",
            "aifactory-governance/gov-cross-charging.yaml",
            "variables/persona-access-steps.yaml",
            "variables/logic-app-network-steps.yaml",
        ):
            self.assertTrue((self.root / consumer.ADO / relative).is_file(), relative)
        self.assertFalse((self.root / consumer.ADO / "esml-infra-project/infra-project-esml.yaml").exists())

    def test_migration_archives_only_unchanged_legacy_files(self):
        obsolete = self.root / ".github/workflows/infra-project-esml.yml"
        obsolete.parent.mkdir(parents=True)
        original = b"# unchanged legacy template fixture\n"
        obsolete.write_bytes(original)
        env = {**os.environ, "GIT_AUTHOR_NAME": "Consumer Test", "GIT_AUTHOR_EMAIL": "test@example.invalid",
               "GIT_COMMITTER_NAME": "Consumer Test", "GIT_COMMITTER_EMAIL": "test@example.invalid"}
        for args in (["init", "-b", "fixture"], ["add", "."], ["commit", "-m", "Legacy fixture"]):
            subprocess.run(["git", "-C", str(self.root), *args], env=env, capture_output=True, check=True)
        baseline = consumer.git(self.root, "rev-parse", "HEAD").decode().strip()
        with mock.patch.object(consumer, "LEGACY_BASELINE", baseline):
            self.install(dry_run=True)
            self.assertTrue(obsolete.exists())
            self.install()
            self.assertFalse(obsolete.exists())
            backups = list((self.root / ".aifactory-backups").glob("legacy-*/.github/workflows/infra-project-esml.yml"))
            self.assertEqual(len(backups), 1)
            self.assertEqual(backups[0].read_bytes(), original)
            before = self.snapshot()
            self.install()
            self.assertEqual(before, self.snapshot())

    def test_modified_obsolete_workflow_is_preserved_and_blocks_all_writes(self):
        obsolete = self.root / ".github/workflows/infra-project-esml.yml"
        obsolete.parent.mkdir(parents=True)
        obsolete.write_text("# customer workflow\n")
        before = self.snapshot()
        with self.assertRaisesRegex(ValueError, "legacy.*review|review.*migration"):
            self.install()
        self.assertEqual(before, self.snapshot())

    def test_existing_active_config_survives_dry_run_byte_for_byte(self):
        self.install()
        config = self.root / "aifactory/variables.json"
        config.write_bytes(b'{"dev":{"customer":"unchanged"}}\r\n')
        before = self.snapshot()
        self.install(dry_run=True)
        self.assertEqual(before, self.snapshot())

    def test_refresh_preserves_git_checkout_line_endings(self):
        self.install()
        for relative in (".github/workflows/infra-common.yml", "aifactory/variables-template.json",
                         "aifactory/esml-infra/azure-devops/bicep/yaml/variables/variables-template.yaml"):
            path = self.root / relative
            path.write_bytes(consumer.normalized(path.read_bytes()).replace(b"\n", b"\r\n"))
        before = self.snapshot()
        self.install()
        self.assertEqual(before, self.snapshot())

    def test_common_promotion_requires_explicit_prerequisite_scope(self):
        with self.assertRaisesRegex(ValueError, "prerequisite"):
            consumer.dispatch_command("common", "org/repo", "consumer-branch", "prod")
        command = consumer.dispatch_command("common", "org/repo", "consumer-branch", "prod",
                                            include_common_prerequisites=True)
        for field in ("deploy_dev=true", "deploy_stage=true", "deploy_prod=true",
                      "use_json_config_override=false"):
            self.assertIn(field, command)
        command = consumer.dispatch_command("common", "org/repo", "consumer-branch", "dev")
        self.assertIn("deploy_stage=false", command)
        self.assertIn("deploy_prod=false", command)

    def test_common_json_identity_is_explicit_not_forced_for_credentials_mode(self):
        command = consumer.dispatch_command("common", "org/repo", "consumer-branch", "dev")
        self.assertIn("use_json_config_override=false", command)
        command = consumer.dispatch_command("common", "org/repo", "consumer-branch", "dev",
                                            use_json_config_override=True)
        self.assertIn("use_json_config_override=true", command)

    def test_deploy_without_execute_never_calls_gh(self):
        self.install()
        (self.root / consumer.SUBMODULE).mkdir()
        (self.root / consumer.SUBMODULE / ".git").write_text("fixture")
        with mock.patch.object(consumer, "ensure_submodule", return_value=self.source), \
                mock.patch.object(consumer.subprocess, "run") as run, \
                contextlib.redirect_stdout(io.StringIO()):
            code = consumer.main(["deploy", "--root", str(self.root), "--repo", "org/repo",
                                  "--ref", "consumer-branch", "--dry-run"])
        self.assertEqual(code, 0)
        run.assert_not_called()

    def test_default_dispatch_ref_is_current_branch_and_detached_head_fails(self):
        self.install()
        (self.root / consumer.SUBMODULE).mkdir()
        (self.root / consumer.SUBMODULE / ".git").write_text("fixture")
        for branch, expected in ((b"customer-branch\n", 0), (b"", 2)):
            with self.subTest(branch=branch):
                output, errors = io.StringIO(), io.StringIO()
                with mock.patch.object(consumer, "ensure_submodule", return_value=self.source), \
                        mock.patch.object(consumer, "git", return_value=branch), \
                        contextlib.redirect_stdout(output), contextlib.redirect_stderr(errors):
                    code = consumer.main(["deploy", "--root", str(self.root), "--repo", "org/repo"])
                self.assertEqual(code, expected)
                if branch:
                    self.assertIn("--ref customer-branch", output.getvalue())
                else:
                    self.assertIn("branch/ref", errors.getvalue())

    def test_dispatch_failure_returns_nonzero_without_success_claim(self):
        self.install()
        (self.root / consumer.SUBMODULE).mkdir()
        (self.root / consumer.SUBMODULE / ".git").write_text("fixture")
        stdout, stderr = io.StringIO(), io.StringIO()
        with mock.patch.object(consumer, "ensure_submodule", return_value=self.source), \
                mock.patch.object(consumer, "validate_dispatch_ref"), \
                mock.patch.object(consumer.subprocess, "run", return_value=mock.Mock(returncode=1)), \
                contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            code = consumer.main(["deploy", "--root", str(self.root), "--repo", "org/repo",
                                  "--ref", "consumer-branch", "--execute"])
        self.assertEqual(code, 2)
        self.assertIn("ERROR", stderr.getvalue())
        self.assertNotIn("accepted", stdout.getvalue())

    def test_custom_workflow_is_not_overwritten(self):
        path = self.root / ".github/workflows/infra-common.yml"
        path.parent.mkdir(parents=True)
        path.write_text("# user workflow\n")
        with self.assertRaisesRegex(ValueError, "modified|conflict|review"):
            self.install()
        self.assertEqual(path.read_text(), "# user workflow\n")
        self.assertFalse((self.root / "aifactory").exists())

    def test_dispatch_requires_explicit_target_repository_and_known_target(self):
        with self.assertRaises(ValueError):
            consumer.dispatch_command("project", "", "release/v1.25", "dev")
        with self.assertRaises(ValueError):
            consumer.dispatch_command("infra-project-esml", "org/repo", "branch", "dev")
        command = consumer.dispatch_command("project", "org/repo", "feature/setup", "stage")
        self.assertIn("infra-project.yml", command)
        self.assertIn("feature/setup", command)
        self.assertIn("environment=stage", command)
        self.assertNotIn("main", command)

    def test_other_cwd_and_explicit_failure(self):
        result = subprocess.run(
            [sys.executable, "-B", str(ROOT / "bootstrap/consumer.py"), "refresh",
             "--root", str(self.root), "--dry-run"], cwd=self.root,
            capture_output=True, text=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("ERROR", result.stderr)
        self.assertNotIn("Success", result.stdout)
        self.assertEqual(list(self.root.iterdir()), [])

    def test_default_root_is_script_relative_from_other_cwd(self):
        result = subprocess.run(
            [sys.executable, "-B", str(ROOT / "bootstrap/consumer.py"), "refresh", "--dry-run"],
            cwd=self.root, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("no files changed", result.stdout)
        self.assertEqual(list(self.root.iterdir()), [])

    def test_shell_entrypoints_probe_python_runtime(self):
        for name in ("01b-BYORepo-init-template-files-once.sh",
                     "03b-GH-add-aifactory-pipelines-once.sh", "04ab-setup-infra-aifactory.sh"):
            text = (ROOT / name).read_text(encoding="utf-8")
            self.assertIn("python3 -c 'import sys; sys.exit(sys.version_info < (3, 9))'", text)
            self.assertIn("python -c 'import sys; sys.exit(sys.version_info < (3, 9))'", text)

    def test_source_and_checked_in_workflow_copies_are_consistent(self):
        for workflow in consumer.WORKFLOWS:
            self.assertEqual(
                consumer.normalized((ROOT / ".github/workflows" / workflow).read_bytes()),
                consumer.normalized(consumer.render_workflow(self.source / consumer.SETTINGS / "github-actions" / workflow)))
        for name in consumer.OBSOLETE_WORKFLOWS:
            self.assertFalse((ROOT / ".github/workflows" / name).exists())
        self.assertEqual(list((ROOT / "aifactory/parameters").glob("*.json")), [])

    def test_explicit_credentials_mode_overrides_stale_oidc_secret(self):
        source = self.source / consumer.SETTINGS / "github-actions/infra-project-phase.yml"
        rendered = consumer.render_workflow(source).decode()
        oidc = consumer.OIDC_CONDITION
        credentials = consumer.CREDENTIALS_CONDITION
        self.assertIn(oidc, rendered)
        self.assertIn(credentials, rendered)
        def evaluate(expression, mode, client):
            expression = expression.replace("vars.AZURE_AUTH_MODE", repr(mode))
            expression = expression.replace("env.AZURE_CLIENT_ID", repr(client))
            return eval(expression.replace("&&", " and ").replace("||", " or "), {"__builtins__": {}})
        for mode, client, expected_oidc in (
            ("credentials", "stale-client", False), ("oidc", "client", True),
            ("oidc", "", True), ("", "existing-client", True), ("", "", False),
        ):
            self.assertEqual(evaluate(oidc, mode, client), expected_oidc)
            self.assertEqual(evaluate(credentials, mode, client), not expected_oidc)

    def test_optional_workflows_support_both_auth_modes_without_widening_gateway_plan(self):
        for name in ("infra-ai-gateway.yml", "infra-project-dashboards.yml", "infra-project-healthmodel.yml"):
            text = consumer.render_workflow(self.source / consumer.SETTINGS / "github-actions" / name).decode()
            self.assertIn("vars.AZURE_AUTH_MODE", text)
            self.assertIn("creds: ${{ secrets.AZURE_CREDENTIALS }}", text)
            self.assertIn("client-id: ${{ secrets.AZURE_CLIENT_ID }}", text)
            self.assertIn("tenant-id: ${{ secrets.TENANT_ID }}", text)
            self.assertIn("id-token: write", text)
            self.assertIn("Validate BLUE authentication selection", text)
        gateway = consumer.render_workflow(
            self.source / consumer.SETTINGS / "github-actions/infra-ai-gateway.yml").decode()
        self.assertEqual(gateway.count(consumer.GATEWAY_LOGIN_GATE), 2)

    def test_json_identity_rejects_conflicting_credentials_selection(self):
        for name, flag in (("infra-common.yml", "use_json_config_override"),
                           ("infra-project-phase.yml", "json_identity_auth")):
            text = consumer.render_workflow(self.source / consumer.SETTINGS / "github-actions" / name).decode()
            self.assertIn("BLUE_JSON_IDENTITY: ${{ inputs." + flag + " }}", text)
            self.assertIn("JSON identity requires OIDC", text)


if __name__ == "__main__":
    unittest.main()
