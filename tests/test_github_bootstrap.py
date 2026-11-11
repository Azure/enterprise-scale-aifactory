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
    }


class EnvironmentTests(unittest.TestCase):
    def test_registered_minimal_values_need_no_legacy_infrastructure_configuration(self):
        values = {key: value for key, value in valid_values().items()
                  if key in {"TENANT_ID", "DEV_SUBSCRIPTION_ID", "DEV_AZURE_CLIENT_ID"}}
        self.assertEqual(gb.build_plan(values, ["dev"], "oidc"), {
            "dev": {
                "variables": {"AZURE_SUBSCRIPTION_ID": values["DEV_SUBSCRIPTION_ID"]},
                "secrets": {"TENANT_ID": values["TENANT_ID"],
                            "AZURE_CLIENT_ID": values["DEV_AZURE_CLIENT_ID"]},
            },
        })

    def test_obsolete_settings_rejected_instead_of_silently_accepted(self):
        for key in ("AIFACTORY_PREFIX", "LAKE_PREFIX", "DEV_CIDR_RANGE",
                    "ENABLE_APIM", "DEV_VNET_IP_RANGE", "PROJECT_TYPE",
                    "AIFACTORY_GITHUB_ENVIRONMENTS", "DEV_AZURE_CREDENTIALS"):
            values = {name: value for name, value in valid_values().items()
                      if name in {"TENANT_ID", "DEV_SUBSCRIPTION_ID", "DEV_AZURE_CLIENT_ID"}}
            values[key] = ""
            with self.subTest(key=key), self.assertRaisesRegex(gb.BootstrapError, "Unsupported"):
                gb.build_plan(values, ["dev"], "oidc")

    def test_single_writer_oidc_matches_public_enrollment_variables(self):
        values = {key: value for key, value in valid_values().items()
                  if key in {"TENANT_ID", "DEV_SUBSCRIPTION_ID", "DEV_AZURE_CLIENT_ID"}}
        plan = gb.build_plan(values, ["dev"], "oidc-single-writer")["dev"]
        self.assertEqual(plan["secrets"], {})
        self.assertEqual(plan["variables"], {
            "AZURE_CLIENT_ID": values["DEV_AZURE_CLIENT_ID"],
            "AZURE_TENANT_ID": values["TENANT_ID"],
            "AZURE_SUBSCRIPTION_ID": values["DEV_SUBSCRIPTION_ID"],
        })

    def test_registered_auth_namespace_is_explicit_and_not_an_azure_environment_translation(self):
        values = {key: value for key, value in valid_values().items()
                  if key in {"TENANT_ID", "DEV_SUBSCRIPTION_ID", "DEV_AZURE_CLIENT_ID"}}
        values["DEV_GITHUB_ENVIRONMENT"] = "factory-001-dev"
        self.assertEqual(set(gb.build_plan(values, ["dev"], "oidc")), {"factory-001-dev"})

    def test_namespace_rejects_ambiguous_names_and_duplicate_targets(self):
        for namespace in ("", "<namespace>", "../other", "name/other", "a" * 129):
            with self.subTest(namespace=namespace), self.assertRaises(gb.BootstrapError):
                gb.build_plan({**valid_values(), "DEV_GITHUB_ENVIRONMENT": namespace}, ["dev"], "oidc")
        values = {**valid_values(), "STAGE_SUBSCRIPTION_ID": valid_values()["DEV_SUBSCRIPTION_ID"],
                  "STAGE_AZURE_CLIENT_ID": valid_values()["DEV_AZURE_CLIENT_ID"],
                  "STAGE_GITHUB_ENVIRONMENT": "DEV"}
        with self.assertRaisesRegex(gb.BootstrapError, "distinct GitHub"):
            gb.build_plan(values, ["dev", "stage"], "oidc")

    def test_selected_identity_uuid_validation_never_discloses_values(self):
        for key in valid_values():
            for value in ("not-a-uuid-private-value", "00000000-0000-0000-0000-000000000000"):
                with self.subTest(key=key, value=value), self.assertRaises(gb.BootstrapError) as raised:
                    gb.build_plan({**valid_values(), key: value}, ["dev"], "oidc")
                self.assertNotIn(value, str(raised.exception))

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

    def test_selected_environment_only_without_legacy_stage_translation(self):
        values = valid_values()
        values["PROD_SUBSCRIPTION_ID"] = "<todo>"
        plan = gb.build_plan(values, ["dev"], "oidc")
        self.assertEqual(set(plan), {"dev"})
        self.assertNotIn("AZURE_ENV_NAME", plan["dev"]["variables"])
        values.update(STAGE_SUBSCRIPTION_ID=values["DEV_SUBSCRIPTION_ID"],
                      STAGE_AZURE_CLIENT_ID=values["DEV_AZURE_CLIENT_ID"])
        self.assertEqual(set(gb.build_plan(values, ["stage"], "oidc")), {"stage"})
        with self.assertRaises(gb.BootstrapError):
            gb.build_plan(values, ["prod"], "oidc")

    def test_missing_and_placeholder_required_values_fail(self):
        for value in ["", "<todo>", "replace_with_dev_sp_credentials"]:
            values = valid_values()
            values["DEV_SUBSCRIPTION_ID"] = value
            with self.subTest(value=value), self.assertRaises(gb.BootstrapError):
                gb.build_plan(values, ["dev"], "oidc")

    def test_omitted_blank_and_placeholder_sync_settings_preserved(self):
        values = valid_values()
        values.update(DEV_AZURE_CLIENT_ID="", DEV_SUBSCRIPTION_ID="<subscription-uuid>")
        del values["TENANT_ID"]
        plan = gb.build_plan(values, ["dev"], "oidc", initial=False)["dev"]
        self.assertEqual(plan, {"variables": {}, "secrets": {}})

    def test_credential_json_is_not_a_supported_template_fallback(self):
        values = valid_values()
        for credential in ["replace_with_credentials", '{"clientSecret":"<todo>"}',
                           json.dumps({"clientId": values["DEV_AZURE_CLIENT_ID"],
                                       "clientSecret": "a real secret",
                                       "tenantId": values["TENANT_ID"],
                                       "subscriptionId": values["DEV_SUBSCRIPTION_ID"]})]:
            values["DEV_AZURE_CREDENTIALS"] = credential
            with self.assertRaises(gb.BootstrapError) as raised:
                gb.build_plan(values, ["dev"], "credentials")
            self.assertNotIn(credential, str(raised.exception))
        with self.assertRaisesRegex(gb.BootstrapError, "do not support AZURE_CREDENTIALS"):
            gb.build_plan(valid_values(), ["dev"], "credentials")

    def test_sync_preserves_blank_auth_secrets(self):
        values = valid_values()
        values["DEV_AZURE_CLIENT_ID"] = ""
        plan = gb.build_plan(values, ["dev"], "oidc", initial=False)["dev"]
        self.assertNotIn("AZURE_CLIENT_ID", plan["secrets"])

    def test_selected_environment_overrides_common_identity(self):
        values = valid_values()
        values.update(DEV_TENANT_ID="44444444-4444-4444-4444-444444444444",
                      AZURE_CLIENT_ID="55555555-5555-5555-5555-555555555555")
        secrets = gb.build_plan(values, ["dev"], "oidc")["dev"]["secrets"]
        self.assertEqual(secrets["TENANT_ID"], values["DEV_TENANT_ID"])
        self.assertEqual(secrets["AZURE_CLIENT_ID"], values["DEV_AZURE_CLIENT_ID"])

    def test_initial_and_sync_have_identical_mapping(self):
        values = valid_values()
        self.assertEqual(gb.build_plan(values, ["dev"], "oidc"),
                         gb.build_plan(values, ["dev"], "oidc", initial=False))

    def test_obsolete_repository_scoped_environment_routing_is_rejected(self):
        values = valid_values()
        values["AIFACTORY_GITHUB_ENVIRONMENTS"] = '{"dev":"custom-dev"}'
        with self.assertRaisesRegex(gb.BootstrapError, "Unsupported"):
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

    def test_exact_pinned_scoped_workflow_authentication_is_classified(self):
        mapping = gb.load_mapping()
        upstream = ROOT / "azure-enterprise-scale-ml"
        self.assertEqual(mapping["upstream_commit"], "89eca66185366a702b026cec8c938570548c649c")
        self.assertNotIn("optional_variables", mapping)
        for mode, contract in mapping["auth_modes"].items():
            path = upstream.joinpath(*contract["workflow"].split("/"))
            workflow = path.read_text(encoding="utf-8")
            self.assertIn("id-token: write", workflow)
            self.assertIn("environment: ${{ inputs.auth_namespace }}", workflow)
            self.assertNotIn("AZURE_CREDENTIALS", workflow)
            for context, kind in [("vars", "variables"), ("secrets", "secrets")]:
                refs = set(re.findall(r"\b" + context + r"\.([A-Za-z0-9_]+)", workflow))
                mapped = {name for name, definition in mapping[kind].items()
                          if definition.get("auth", mode) == mode}
                self.assertEqual(refs, mapped)


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
            return '{"secrets":[{"name":"AZURE_CLIENT_ID"},{"name":"TENANT_ID"}]}'
        if args[:3] == ["gh", "api", "repos/owner/dest/environments/dev/variables"]:
            return '{"variables":[]}'
        return "{}"


class OrchestrationTests(unittest.TestCase):
    def test_auth_mode_requires_explicit_choice_before_any_tools(self):
        values = self.policy_values()
        del values["GITHUB_AUTH_MODE"]
        runner = FakeRunner()
        with self.assertRaisesRegex(gb.BootstrapError, "GITHUB_AUTH_MODE"):
            gb.execute(gb.parser().parse_args(["sync"]), values, runner)
        self.assertEqual(runner.calls, [])

    def test_selected_source_must_be_v125_or_later_release_before_any_tools(self):
        for branch in ("main", "release/v1.24", "release/v0.99", "release/v1.25-preview"):
            values = self.policy_values()
            values["GITHUB_SOURCE_BRANCH"] = values["GITHUB_DEFAULT_BRANCH"] = branch
            runner = FakeRunner()
            with self.subTest(branch=branch), self.assertRaisesRegex(gb.BootstrapError, "v1.25"):
                gb.execute(gb.parser().parse_args(["mirror"]), values, runner)
            self.assertEqual(runner.calls, [])

    def test_default_destination_branch_follows_selected_release(self):
        values = self.policy_values()
        values["GITHUB_SOURCE_BRANCH"] = "release/v1.26"
        del values["GITHUB_DEFAULT_BRANCH"]
        options = gb.resolve_options(gb.parser().parse_args(["mirror"]), values)
        self.assertEqual(options.default_branch, "release/v1.26")

    def test_missing_source_release_does_not_fall_back_to_main(self):
        values = self.policy_values()
        del values["GITHUB_SOURCE_BRANCH"]
        runner = FakeRunner()
        with self.assertRaisesRegex(gb.BootstrapError, "GITHUB_SOURCE_BRANCH"):
            gb.execute(gb.parser().parse_args(["mirror"]), values, runner)
        self.assertEqual(runner.calls, [])

    def test_unsupported_infrastructure_keys_fail_before_tools(self):
        runner = FakeRunner()
        with self.assertRaisesRegex(gb.BootstrapError, "Unsupported"):
            gb.execute(self.options("sync"), {**valid_values(), "DEV_ENABLE_APIM": "true"}, runner)
        self.assertEqual(runner.calls, [])

    def test_single_writer_mode_requires_private_destination(self):
        runner = FakeRunner()
        with self.assertRaisesRegex(gb.BootstrapError, "private"):
            gb.execute(self.options(extra=["--auth-mode", "oidc-single-writer", "--visibility", "public"]),
                       valid_values(), runner)
        self.assertEqual(runner.calls, [])
        runner = FakeRunner(overrides={("gh", "api", "repos/owner/dest"): json.dumps({
            "full_name": "owner/dest", "visibility": "public", "permissions": {"admin": True, "push": True}})})
        with self.assertRaises(gb.BootstrapError):
            gb.execute(self.options("sync", ["--auth-mode", "oidc-single-writer"]), valid_values(), runner)
        self.assertFalse(any("set" in args for args, _ in runner.calls))

    def test_custom_namespace_is_used_for_reads_and_writes_only(self):
        namespace = "factory-001-dev"
        runner = FakeRunner(overrides={
            ("gh", "api", "repos/owner/dest/environments"): json.dumps({"environments": [{"name": namespace}]}),
            ("gh", "api", f"repos/owner/dest/environments/{namespace}/variables"): '{"variables":[]}',
            ("gh", "api", f"repos/owner/dest/environments/{namespace}/secrets"): '{"secrets":[]}',
        })
        with contextlib.redirect_stdout(io.StringIO()):
            gb.execute(self.options("sync"), {**valid_values(), "DEV_GITHUB_ENVIRONMENT": namespace}, runner)
        for args, _ in runner.calls:
            if "set" in args:
                self.assertEqual(args[-2:], ["--env", namespace])
            self.assertNotIn("repos/owner/dest/environments/dev/secrets", args)
            self.assertFalse(any("register.json" in arg or "factory-lifecycle" in arg for arg in args))

    def test_existing_environment_case_does_not_trigger_protection_overwrite(self):
        runner = FakeRunner(overrides={
            ("gh", "api", "repos/owner/dest/environments"): '{"environments":[{"name":"Dev"}]}',
        })
        with self.assertRaisesRegex(gb.BootstrapError, "exact spelling"):
            gb.execute(self.options("sync"), valid_values(), runner)
        self.assertFalse(any("PUT" in args or "set" in args for args, _ in runner.calls))

    def test_sync_can_preserve_all_existing_authentication_settings(self):
        for mode in ("oidc", "oidc-single-writer"):
            expected = gb.build_plan(valid_values(), ["dev"], mode)["dev"]["variables"]
            runner = FakeRunner(overrides={
                ("gh", "api", "repos/owner/dest/environments/dev/variables"): json.dumps(
                    {"variables": [{"name": name, "value": value} for name, value in expected.items()]}),
            })
            with self.subTest(mode=mode), contextlib.redirect_stdout(io.StringIO()):
                gb.execute(self.options("sync", ["--auth-mode", mode]), {}, runner)
            self.assertFalse(any("set" in args or "PUT" in args or "DELETE" in args for args, _ in runner.calls))

    def test_missing_or_invalid_remote_public_identity_blocks_without_disclosing_it(self):
        for remote in ([], [{"name": "AZURE_SUBSCRIPTION_ID", "value": "private-invalid-value"}],
                       [{"name": "AZURE_SUBSCRIPTION_ID", "value": None}]):
            runner = FakeRunner(overrides={
                ("gh", "api", "repos/owner/dest/environments/dev/variables"): json.dumps({"variables": remote}),
            })
            with self.subTest(remote=remote), self.assertRaises(gb.BootstrapError) as raised:
                gb.execute(self.options("sync"), {}, runner)
            self.assertNotIn("private-invalid-value", str(raised.exception))
            self.assertFalse(any("set" in args or "PUT" in args for args, _ in runner.calls))

    def test_new_environment_cannot_rely_on_repository_authentication_fallback(self):
        runner = FakeRunner(overrides={
            ("gh", "api", "repos/owner/dest/environments"): '{"environments":[]}',
        })
        with self.assertRaises(gb.BootstrapError):
            gb.execute(self.options("sync"), {}, runner)
        self.assertFalse(any("set" in args or "PUT" in args for args, _ in runner.calls))

    def test_paginated_settings_require_all_valid_pages_before_any_mutation(self):
        for response in ("[]", '[{"variables":[]},{}]', "null"):
            runner = FakeRunner(overrides={
                ("gh", "api", "repos/owner/dest/environments/dev/variables"): response,
            })
            with self.subTest(response=response), self.assertRaises(gb.BootstrapError):
                gb.execute(self.options("sync"), valid_values(), runner)
            self.assertFalse(any("set" in args or "PUT" in args for args, _ in runner.calls))

    def test_sync_single_writer_writes_only_public_identity_variables(self):
        runner = FakeRunner()
        with contextlib.redirect_stdout(io.StringIO()):
            gb.execute(self.options("sync", ["--auth-mode", "oidc-single-writer"]), valid_values(), runner)
        written = {args[3] for args, _ in runner.calls if args[:3] == ["gh", "variable", "set"]}
        self.assertEqual(written, {"AZURE_CLIENT_ID", "AZURE_TENANT_ID", "AZURE_SUBSCRIPTION_ID"})
        self.assertFalse(any(args[:2] == ["gh", "secret"] or "DELETE" in args for args, _ in runner.calls))

    def options(self, command="mirror", extra=()):
        args = [command, "--destination", "owner/dest", "--environments", "dev", "--auth-mode", "oidc"]
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

    def test_legacy_repository_routing_does_not_control_registered_namespaces(self):
        response = {"variables": [{"name": "AIFACTORY_GITHUB_ENVIRONMENTS",
                                   "value": '{"dev":"custom-dev"}'}]}
        runner = FakeRunner(overrides={("gh", "api", "repos/owner/dest/actions/variables"): json.dumps(response)})
        with contextlib.redirect_stdout(io.StringIO()):
            gb.execute(self.options("sync"), valid_values(), runner)
        self.assertTrue(any("set" in a and "--env" in a and "dev" in a for a, _ in runner.calls))
        self.assertFalse(any("custom-dev" in a or "AIFACTORY_GITHUB_ENVIRONMENTS" in a for a, _ in runner.calls))

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
