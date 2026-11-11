import contextlib
import io
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from bootstrap import github_bootstrap as gb


ROOT = Path(__file__).resolve().parents[1]


def valid_values():
    return {
        "TENANT_ID": "11111111-1111-1111-1111-111111111111",
        "DEV_SUBSCRIPTION_ID": "22222222-2222-2222-2222-222222222222",
        "DEV_AZURE_CLIENT_ID": "33333333-3333-3333-3333-333333333333",
        "AIFACTORY_LOCATION": "swedencentral",
        "AIFACTORY_LOCATION_SHORT": "sdc",
        "AIFACTORY_PREFIX": "acme",
        "AIFACTORY_SUFFIX": "-001",
        "LAKE_PREFIX": "acmelake",
        "AIFACTORY_SEEDING_KEYVAULT_NAME": "seed-vault",
        "AIFACTORY_SEEDING_KEYVAULT_RG": "seed-rg",
        "AIFACTORY_SEEDING_KEYVAULT_SUBSCRIPTION_ID": "22222222-2222-2222-2222-222222222222",
        "PROJECT_NUMBER": "001",
        "DEV_CIDR_RANGE": "20",
    }


class EnvironmentTests(unittest.TestCase):
    def parse(self, content):
        with tempfile.TemporaryDirectory(dir=ROOT, prefix=".bootstrap-test-") as directory:
            path = Path(directory) / ".env"
            path.write_text(content, encoding="utf-8")
            return gb.parse_env(path)

    def test_quotes_spaces_comments_and_no_execution(self):
        self.assertEqual(self.parse(
            'NAME = "hello world # literal" # comment\n'
            "JSON='{\"clientSecret\":\"do not print\"}'\n"
            'LITERAL="$(touch forbidden)"\nEMPTY=\n'
        ), {"NAME": "hello world # literal", "JSON": '{"clientSecret":"do not print"}',
            "LITERAL": "$(touch forbidden)", "EMPTY": ""})

    def test_duplicates_and_bad_syntax_fail(self):
        for content in ["A=1\nA=2", "A='unterminated", "source other.env", "export A=1"]:
            with self.subTest(content=content), self.assertRaises(gb.BootstrapError):
                self.parse(content)

    def test_template_parses_without_duplicate_keys(self):
        gb.parse_env(ROOT / ".env.template")

    def test_selected_environment_only_and_stage_translation(self):
        values = valid_values()
        values["PROD_SUBSCRIPTION_ID"] = "<todo>"
        plan = gb.build_plan(values, ["dev"], "oidc")
        self.assertEqual(plan["dev"]["variables"]["AZURE_ENV_NAME"], "dev")
        values.update(STAGE_SUBSCRIPTION_ID=values["DEV_SUBSCRIPTION_ID"],
                      STAGE_AZURE_CLIENT_ID=values["DEV_AZURE_CLIENT_ID"],
                      STAGE_CIDR_RANGE="30")
        self.assertEqual(gb.build_plan(values, ["stage"], "oidc")["stage"]["variables"]["AZURE_ENV_NAME"], "test")
        with self.assertRaises(gb.BootstrapError):
            gb.build_plan(values, ["prod"], "oidc")

    def test_missing_and_placeholder_required_values_fail(self):
        for value in ["", "<todo>", "replace_with_dev_sp_credentials"]:
            values = valid_values()
            values["AIFACTORY_PREFIX"] = value
            with self.subTest(value=value), self.assertRaises(gb.BootstrapError):
                gb.build_plan(values, ["dev"], "oidc")

    def test_omitted_blank_optional_settings_preserved(self):
        values = valid_values()
        values.update(PROJECT_MEMBERS="", ENABLE_APIM="", AIFACTORY_SALT="<5chars>")
        plan = gb.build_plan(values, ["dev"], "oidc")["dev"]
        self.assertNotIn("PROJECT_MEMBERS", plan["secrets"])
        self.assertNotIn("ENABLE_APIM", plan["variables"])
        self.assertNotIn("AIFACTORY_SALT", plan["variables"])
        self.assertNotIn("AZURE_CREDENTIALS", plan["secrets"])

    def test_real_credentials_required_and_checked(self):
        values = valid_values()
        for credential in ["replace_with_credentials", '{"clientSecret":"<todo>"}']:
            values["DEV_AZURE_CREDENTIALS"] = credential
            with self.assertRaises(gb.BootstrapError):
                gb.build_plan(values, ["dev"], "credentials")
        values["DEV_AZURE_CREDENTIALS"] = json.dumps({
            "clientId": values["DEV_AZURE_CLIENT_ID"], "clientSecret": "a real secret",
            "tenantId": values["TENANT_ID"], "subscriptionId": values["DEV_SUBSCRIPTION_ID"]})
        plan = gb.build_plan(values, ["dev"], "credentials")["dev"]
        self.assertEqual(plan["secrets"]["AZURE_CREDENTIALS"], values["DEV_AZURE_CREDENTIALS"])
        self.assertNotIn("AZURE_CLIENT_ID", plan["secrets"])
        for secret in ("dummy", "change_me", "replace_me"):
            payload = json.loads(values["DEV_AZURE_CREDENTIALS"])
            payload["clientSecret"] = secret
            values["DEV_AZURE_CREDENTIALS"] = json.dumps(payload)
            with self.subTest(secret=secret), self.assertRaises(gb.BootstrapError):
                gb.build_plan(values, ["dev"], "credentials")

    def test_sync_preserves_blank_auth_secrets(self):
        values = valid_values()
        values["DEV_AZURE_CLIENT_ID"] = ""
        plan = gb.build_plan(values, ["dev"], "oidc", initial=False)["dev"]
        self.assertNotIn("AZURE_CLIENT_ID", plan["secrets"])

    def test_selected_environment_overrides_and_legacy_aliases(self):
        values = valid_values()
        values.update(ENABLE_APIM="false", DEV_ENABLE_APIM="true", PROJECT_TYPE="genai-1",
                      DEV_VNET_IP_RANGE="10.20.0.0/16")
        variables = gb.build_plan(values, ["dev"], "oidc")["dev"]["variables"]
        self.assertEqual(variables["ENABLE_APIM"], "true")
        self.assertEqual(variables["ADMIN_PROJECT_TYPE"], "genai-1")
        self.assertEqual(variables["CIDR_RANGE"], "20")
        self.assertEqual(variables["COMMON_VNET_CIDR"], "10.20.0.0/16")

    def test_initial_and_sync_have_identical_mapping(self):
        values = valid_values()
        self.assertEqual(gb.build_plan(values, ["dev"], "oidc"),
                         gb.build_plan(values, ["dev"], "oidc", initial=False))

    def test_repository_scoped_environment_routing_is_not_silently_misscoped(self):
        values = valid_values()
        values["AIFACTORY_GITHUB_ENVIRONMENTS"] = '{"dev":"custom-dev"}'
        with self.assertRaisesRegex(gb.BootstrapError, "repository-scoped"):
            gb.build_plan(values, ["dev"], "oidc")

    def test_empty_duplicate_or_unknown_environment_rejected(self):
        for environments in ([], ["dev", "dev"], ["test"], ["stage", ""]):
            with self.subTest(environments=environments), self.assertRaises(gb.BootstrapError):
                gb.build_plan(valid_values(), environments, "oidc")

    def test_repository_identity_validation(self):
        for repository in ("https://github.com/owner/repo", "../checkout", "owner/..", "owner/.git"):
            with self.subTest(repository=repository), self.assertRaises(gb.BootstrapError):
                gb.repository_name(repository)
        self.assertEqual(gb.repository_name("Owner/Repo.GIT"), "Owner/Repo")

    def test_workflow_references_are_all_classified(self):
        mapping = gb.load_mapping()
        upstream = ROOT / "azure-enterprise-scale-ml" / "environment_setup" / "aifactory" / "bicep" / "copy_to_local_settings" / "github-actions"
        for context, kind in [("vars", "variables"), ("secrets", "secrets")]:
            refs = {name for path in upstream.glob("*.yml")
                    for name in re.findall(r"\b" + context + r"\.([A-Za-z0-9_]+)", path.read_text(encoding="utf-8"))}
            mapped = set(mapping[kind]) | set(mapping.get("optional_" + kind, []))
            self.assertFalse(refs - mapped, f"Unmapped {context}: {sorted(refs - mapped)}")


class RunnerTests(unittest.TestCase):
    @patch("subprocess.run")
    def test_errors_redact_stdout_stderr_and_input(self, run):
        run.return_value = subprocess.CompletedProcess([], 1, "SECRET", "SECRET")
        with self.assertRaises(gb.BootstrapError) as raised:
            gb.Runner().run(["gh", "secret", "set", "NAME"], input_text="SECRET")
        self.assertNotIn("SECRET", str(raised.exception))
        self.assertEqual(run.call_args.kwargs["input"], "SECRET")

    @patch("shutil.which", return_value=None)
    def test_missing_tool_fails(self, which):
        with self.assertRaises(gb.BootstrapError):
            gb.Runner().require_tools(["gh"])


class FakeRunner:
    def __init__(self, fail=None, overrides=None):
        self.calls = []
        self.fail = fail
        self.overrides = overrides or {}

    def require_tools(self, names):
        self.calls.append((["tools"] + names, None))

    def run(self, args, input_text=None, cwd=None):
        self.calls.append((args, input_text))
        if self.fail and self.fail(args):
            raise gb.BootstrapError("redacted command failure")
        if tuple(args[:3]) in self.overrides:
            return self.overrides[tuple(args[:3])]
        if args[:3] == ["gh", "api", "user"]:
            return '{"login":"owner"}'
        if args[:3] == ["gh", "api", "repos/source/template"]:
            return json.dumps({"full_name": "source/template", "permissions": {"pull": True}})
        if args[:3] == ["gh", "api", "repos/owner/dest"]:
            return json.dumps({"full_name": "owner/dest", "visibility": "private",
                               "default_branch": "release/v1.25", "permissions": {"admin": True, "push": True}})
        if args[:3] == ["gh", "api", "orgs/owner/memberships/owner"]:
            return '{"state":"active","role":"admin"}'
        if "ls-remote" in args:
            return "a" * 40 + "\trefs/heads/release/v1.25\n" if "refs/heads/release/v1.25" in args else ""
        if args[:3] == ["gh", "api", "repos/owner/dest/environments"]:
            return '{"environments":[{"name":"dev"}]}'
        if args[:3] == ["gh", "api", "repos/owner/dest/actions/variables"]:
            return '{"variables":[]}'
        if args[:3] == ["gh", "api", "repos/owner/dest/environments/dev/secrets"]:
            return '{"secrets":[{"name":"AZURE_CLIENT_ID"},{"name":"TENANT_ID"},{"name":"AIFACTORY_SEEDING_KEYVAULT_SUBSCRIPTION_ID"}]}'
        if args[:3] == ["gh", "api", "repos/owner/dest/environments/dev/variables"]:
            return '{"variables":[]}'
        return "{}"


class OrchestrationTests(unittest.TestCase):
    def options(self, command="mirror", extra=()):
        args = [command, "--destination", "owner/dest", "--environments", "dev"]
        if command == "mirror":
            args += ["--source", "source/template", "--source-branch", "release/v1.25",
                     "--visibility", "private", "--destination-state", "existing-empty",
                     "--default-branch", "release/v1.25", "--transport", "https"]
        return gb.parser().parse_args(args + list(extra))

    def test_same_repository_case_insensitive_before_tools(self):
        runner = FakeRunner()
        options = self.options(extra=["--source", "OWNER/DEST"])
        with self.assertRaises(gb.BootstrapError):
            gb.execute(options, valid_values(), runner)
        self.assertEqual(runner.calls, [])

    def policy_values(self):
        return {
            **valid_values(),
            "GITHUB_SOURCE_REPO": "source/template",
            "GITHUB_SOURCE_BRANCH": "release/v1.25",
            "GITHUB_DESTINATION_REPO": "owner/dest",
            "GITHUB_VISIBILITY": "private",
            "GITHUB_DESTINATION_STATE": "existing-empty",
            "GITHUB_DEFAULT_BRANCH": "release/v1.25",
            "GITHUB_TRANSPORT": "https",
            "GITHUB_ENVIRONMENTS": "dev",
            "GITHUB_AUTH_MODE": "oidc",
        }

    def test_no_argument_mirror_and_sync_use_local_env_policy(self):
        for command in ("mirror", "sync"):
            runner = FakeRunner()
            options = gb.parser().parse_args([command])
            with self.subTest(command=command), contextlib.redirect_stdout(io.StringIO()):
                gb.execute(options, self.policy_values(), runner)
            self.assertTrue(any("set" in args for args, _ in runner.calls))
            self.assertEqual(any("push" in args for args, _ in runner.calls), command == "mirror")

    def test_cli_policy_overrides_even_invalid_env_policy(self):
        values = self.policy_values()
        for key in values.keys() & {"GITHUB_SOURCE_REPO", "GITHUB_DESTINATION_REPO",
                                    "GITHUB_VISIBILITY", "GITHUB_DESTINATION_STATE",
                                    "GITHUB_TRANSPORT", "GITHUB_ENVIRONMENTS",
                                    "GITHUB_AUTH_MODE", "GITHUB_DEFAULT_BRANCH",
                                    "GITHUB_SOURCE_BRANCH"}:
            values[key] = "<todo>"
        runner = FakeRunner()
        with contextlib.redirect_stdout(io.StringIO()):
            gb.execute(self.options(extra=["--auth-mode", "oidc", "--dry-run"]),
                       values, runner)
        self.assertTrue(runner.calls)

    def test_env_destination_intent_missing_or_placeholder_fails_before_tools(self):
        for value in ("", "<create-or-existing-empty>", "guess"):
            values = self.policy_values()
            values["GITHUB_DESTINATION_STATE"] = value
            runner = FakeRunner()
            with self.subTest(value=value), self.assertRaises(gb.BootstrapError):
                gb.execute(gb.parser().parse_args(["mirror"]), values, runner)
            self.assertEqual(runner.calls, [])

    def test_legacy_repo_and_ssh_aliases_are_safe_data_defaults(self):
        values = self.policy_values()
        for canonical, legacy in [
            ("GITHUB_SOURCE_REPO", "GITHUB_TEMPLATE_REPO"),
            ("GITHUB_DESTINATION_REPO", "GITHUB_NEW_REPO"),
            ("GITHUB_VISIBILITY", "GITHUB_NEW_REPO_VISIBILITY"),
        ]:
            values[legacy] = values.pop(canonical)
        del values["GITHUB_TRANSPORT"]
        values["GITHUB_USE_SSH"] = "true"
        runner = FakeRunner()
        with contextlib.redirect_stdout(io.StringIO()):
            gb.execute(gb.parser().parse_args(["mirror", "--dry-run"]), values, runner)
        self.assertTrue(any("git@github.com:source/template.git" in args for args, _ in runner.calls))

    def test_sync_ignores_unused_mirror_policy_placeholders(self):
        values = self.policy_values()
        values["GITHUB_SOURCE_REPO"] = values["GITHUB_DESTINATION_STATE"] = "<todo>"
        with contextlib.redirect_stdout(io.StringIO()):
            gb.execute(gb.parser().parse_args(["sync"]), values, FakeRunner())

    def test_default_env_file_is_repository_root_when_called_elsewhere(self):
        previous = Path.cwd()
        with tempfile.TemporaryDirectory(dir=ROOT, prefix=".bootstrap-test-") as directory:
            try:
                os.chdir(directory)
                for command in ("mirror", "sync"):
                    self.assertEqual(gb.parser().parse_args([command]).env_file, ROOT / ".env")
                explicit = gb.parser().parse_args(["sync", "--env-file", "caller.env"])
                self.assertEqual(explicit.env_file.resolve(), Path(directory) / "caller.env")
            finally:
                os.chdir(previous)

    def test_main_no_argument_policy_and_explicit_env_from_other_cwd(self):
        previous = Path.cwd()
        with tempfile.TemporaryDirectory(dir=ROOT, prefix=".bootstrap-test-") as directory:
            caller = Path(directory)
            (caller / "caller.env").write_text(
                "\n".join(f"{key}={value}" for key, value in self.policy_values().items()),
                encoding="utf-8")
            try:
                os.chdir(caller)
                for command in ("mirror", "sync"):
                    runner = FakeRunner()
                    with patch.object(gb, "Runner", return_value=runner), contextlib.redirect_stdout(io.StringIO()):
                        self.assertEqual(gb.main([command, "--env-file", "caller.env", "--dry-run"]), 0)
                    self.assertFalse(any("clone" in args or "push" in args or "set" in args for args, _ in runner.calls))
            finally:
                os.chdir(previous)

    def test_configured_template_no_argument_entrypoints_from_other_cwd(self):
        configured = gb.parse_env(ROOT / ".env.template")
        configured.update(self.policy_values())
        previous = Path.cwd()
        with tempfile.TemporaryDirectory(dir=ROOT, prefix=".bootstrap-test-") as directory:
            project = Path(directory) / "project"
            caller = Path(directory) / "elsewhere"
            project.mkdir()
            caller.mkdir()
            (project / ".env").write_text(
                "\n".join(f"{key}='{value}'" for key, value in configured.items()),
                encoding="utf-8")
            (caller / ".env").write_text("GITHUB_DESTINATION_REPO=wrong/repository\n", encoding="utf-8")
            try:
                os.chdir(caller)
                for command in ("mirror", "sync"):
                    runner = FakeRunner()
                    with patch.object(gb, "ROOT", project), patch.object(gb, "Runner", return_value=runner), contextlib.redirect_stdout(io.StringIO()):
                        self.assertEqual(gb.main([command]), 0)
                    self.assertFalse(any("wrong/repository" in argument for args, _ in runner.calls for argument in args))
                    self.assertTrue(any("owner/dest" in argument for args, _ in runner.calls for argument in args))
                    self.assertEqual(any("push" in args for args, _ in runner.calls), command == "mirror")
                self.assertEqual([path.name for path in project.iterdir()], [".env"])
            finally:
                os.chdir(previous)

    def test_conflicting_policy_aliases_fail_before_tools_unless_cli_overridden(self):
        values = self.policy_values()
        values["GITHUB_NEW_REPO"] = "another/destination"
        runner = FakeRunner()
        with self.assertRaisesRegex(gb.BootstrapError, "Conflicting"):
            gb.execute(gb.parser().parse_args(["sync"]), values, runner)
        self.assertEqual(runner.calls, [])
        with contextlib.redirect_stdout(io.StringIO()):
            gb.execute(gb.parser().parse_args(["sync", "--destination", "owner/dest", "--dry-run"]),
                       values, runner)

    def test_dry_run_no_writes_clone_or_secret_output(self):
        runner = FakeRunner()
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            gb.execute(self.options(extra=["--dry-run"]), valid_values(), runner)
        commands = [args for args, _ in runner.calls]
        self.assertFalse(any("clone" in a or "push" in a or "set" in a or "PUT" in a or "PATCH" in a for a in commands))
        self.assertNotIn(valid_values()["TENANT_ID"], output.getvalue())

    def test_sync_never_invokes_git(self):
        runner = FakeRunner()
        gb.execute(self.options("sync"), valid_values(), runner)
        self.assertFalse(any(a[0] == "git" for a, _ in runner.calls))
        secret_calls = [(a, data) for a, data in runner.calls if a[:3] == ["gh", "secret", "set"]]
        self.assertTrue(secret_calls)
        for args, data in secret_calls:
            self.assertIsNotNone(data)
            self.assertNotIn(data, args)
            self.assertNotIn("--body", args)

    def test_auth_api_or_permissions_failure_never_pushes(self):
        for predicate in [
            lambda a: a[:3] == ["gh", "auth", "status"],
            lambda a: a[:3] == ["gh", "api", "repos/owner/dest"],
            lambda a: a[:3] == ["gh", "api", "repos/owner/dest/environments"],
        ]:
            runner = FakeRunner(predicate)
            with self.subTest(predicate=predicate), self.assertRaises(gb.BootstrapError):
                gb.execute(self.options(), valid_values(), runner)
            self.assertFalse(any("push" in a for a, _ in runner.calls))

    def test_denied_permission_bad_json_and_visibility_fail_before_mutation(self):
        for response in ("not json", "null", '{"full_name":"another/repository"}',
                         '{"full_name":"owner/dest","permissions":{"push":true}}',
                         '{"full_name":"owner/dest","permissions":{"admin":true,"push":true},"visibility":"public"}'):
            runner = FakeRunner(overrides={("gh", "api", "repos/owner/dest"): response})
            with self.subTest(response=response), self.assertRaises(gb.BootstrapError):
                gb.execute(self.options(), valid_values(), runner)
            self.assertFalse(any("push" in a or "clone" in a or "set" in a for a, _ in runner.calls))

    def test_nonempty_destination_never_cloned_or_pushed(self):
        runner = FakeRunner(overrides={("git", "ls-remote", "https://github.com/owner/dest.git"):
                                       "a" * 40 + "\trefs/tags/keep\n"})
        with self.assertRaises(gb.BootstrapError):
            gb.execute(self.options(), valid_values(), runner)
        self.assertFalse(any("clone" in a or "push" in a for a, _ in runner.calls))

    def test_generic_not_found_does_not_trigger_create(self):
        runner = FakeRunner(lambda a: a[:3] == ["gh", "api", "repos/owner/dest"])
        with self.assertRaises(gb.BootstrapError):
            gb.execute(self.options(), valid_values(), runner)
        self.assertFalse(any("create" in a or "push" in a for a, _ in runner.calls))

    def test_create_dry_run_does_not_infer_absence(self):
        runner = FakeRunner()
        with contextlib.redirect_stdout(io.StringIO()):
            gb.execute(self.options(extra=["--destination-state", "create", "--dry-run"]),
                       valid_values(), runner)
        self.assertFalse(any("create" in a or "clone" in a or "push" in a for a, _ in runner.calls))
        self.assertFalse(any(a[:3] == ["gh", "api", "repos/owner/dest"] for a, _ in runner.calls))

    def test_sync_missing_required_remote_secret_fails_before_writes(self):
        runner = FakeRunner(overrides={("gh", "api", "repos/owner/dest/environments/dev/secrets"):
                                       '{"secrets":[]}'})
        values = valid_values()
        values["DEV_AZURE_CLIENT_ID"] = ""
        with self.assertRaises(gb.BootstrapError):
            gb.execute(self.options("sync"), values, runner)
        self.assertFalse(any("set" in a or "PUT" in a for a, _ in runner.calls))

    def test_existing_custom_environment_routing_fails_before_writes(self):
        response = {"variables": [{"name": "AIFACTORY_GITHUB_ENVIRONMENTS",
                                   "value": '{"dev":"custom-dev"}'}]}
        runner = FakeRunner(overrides={("gh", "api", "repos/owner/dest/actions/variables"): json.dumps(response)})
        with self.assertRaisesRegex(gb.BootstrapError, "routing"):
            gb.execute(self.options("sync"), valid_values(), runner)
        self.assertFalse(any("set" in a or "PUT" in a for a, _ in runner.calls))

    def test_sync_environment_creation_failure_stops_settings(self):
        runner = FakeRunner(lambda a: "PUT" in a, overrides={
            ("gh", "api", "repos/owner/dest/environments"): '{"environments":[]}'})
        with self.assertRaises(gb.BootstrapError):
            gb.execute(self.options("sync"), valid_values(), runner)
        self.assertFalse(any("set" in a for a, _ in runner.calls))

    def test_existing_environment_is_not_put_and_protection_is_preserved(self):
        runner = FakeRunner()
        with contextlib.redirect_stdout(io.StringIO()):
            gb.execute(self.options("sync"), valid_values(), runner)
        self.assertFalse(any("PUT" in a or "DELETE" in a for a, _ in runner.calls))

    def test_create_failure_never_pushes(self):
        runner = FakeRunner(lambda a: a[:3] == ["gh", "repo", "create"])
        with self.assertRaises(gb.BootstrapError):
            gb.execute(self.options(extra=["--destination-state", "create"]), valid_values(), runner)
        self.assertFalse(any("push" in a for a, _ in runner.calls))

    def test_create_success_requires_post_create_api_preflight(self):
        runner = FakeRunner(lambda a: a[:3] == ["gh", "api", "repos/owner/dest/actions/variables"])
        with self.assertRaises(gb.BootstrapError) as raised:
            gb.execute(self.options(extra=["--destination-state", "create"]), valid_values(), runner)
        self.assertIn("destination repository created", str(raised.exception))
        self.assertFalse(any("clone" in a or "push" in a for a, _ in runner.calls))

    def test_mirror_success_order_and_destination_only_branch_policy(self):
        runner = FakeRunner()
        with contextlib.redirect_stdout(io.StringIO()):
            gb.execute(self.options(), valid_values(), runner)
        commands = [args for args, _ in runner.calls]
        clone = next(index for index, args in enumerate(commands) if "clone" in args)
        push = next(index for index, args in enumerate(commands) if "push" in args)
        branch = next(index for index, args in enumerate(commands) if "PATCH" in args)
        setting = next(index for index, args in enumerate(commands) if "set" in args)
        self.assertLess(clone, push)
        self.assertLess(push, branch)
        self.assertLess(branch, setting)
        self.assertIn("--mirror", commands[clone])
        self.assertIn("--mirror", commands[push])
        self.assertIn("--atomic", commands[push])
        self.assertEqual(commands[branch][2], "repos/owner/dest")
        self.assertFalse(any("checkout" in args or "DELETE" in args for args in commands))

    def test_after_push_failure_reports_partial_progress_without_retry(self):
        runner = FakeRunner(lambda args: "PATCH" in args)
        with self.assertRaises(gb.BootstrapError) as raised:
            gb.execute(self.options(), valid_values(), runner)
        self.assertIn("full Git mirror pushed", str(raised.exception))
        self.assertEqual(sum("push" in args for args, _ in runner.calls), 1)
        self.assertFalse(any("set" in args or "DELETE" in args for args, _ in runner.calls))

    def test_sync_failure_reports_progress_and_stops(self):
        runner = FakeRunner(lambda a: a[:3] == ["gh", "secret", "set"])
        with self.assertRaises(gb.BootstrapError) as raised:
            gb.execute(self.options("sync"), valid_values(), runner)
        self.assertIn("Completed:", str(raised.exception))


if __name__ == "__main__":
    unittest.main()
