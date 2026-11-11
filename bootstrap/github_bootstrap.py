"""Fail-closed GitHub bootstrap. Environment files are data, never shell programs."""

import argparse
import json
import os
from pathlib import Path
import re
import shutil
import stat
import subprocess
import sys
import tempfile
from urllib.parse import quote
import uuid


ROOT = Path(__file__).resolve().parents[1]
ENVIRONMENTS = {"dev": "dev", "stage": "test", "prod": "prod"}


class BootstrapError(Exception):
    pass


def parse_env(path):
    values = {}
    try:
        lines = Path(path).read_text(encoding="utf-8-sig").splitlines()
    except (OSError, UnicodeError):
        raise BootstrapError("Cannot read the local environment file.") from None
    for number, line in enumerate(lines, 1):
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        match = re.fullmatch(r"([A-Za-z_][A-Za-z0-9_]*)\s*=(.*)", line)
        if not match:
            raise BootstrapError(f"Invalid environment assignment on line {number}.")
        key, raw = match.groups()
        if key in values:
            raise BootstrapError(f"Duplicate environment key {key} on line {number}.")
        raw = raw.strip()
        if raw.startswith(("'", '"')):
            delimiter = raw[0]
            result = []
            index = 1
            while index < len(raw):
                char = raw[index]
                if char == delimiter:
                    tail = raw[index + 1:].strip()
                    if tail and not tail.startswith("#"):
                        raise BootstrapError(f"Unexpected text after {key} on line {number}.")
                    break
                if delimiter == '"' and char == "\\" and index + 1 < len(raw) and raw[index + 1] in ('"', "\\"):
                    index += 1
                    char = raw[index]
                result.append(char)
                index += 1
            else:
                raise BootstrapError(f"Unclosed quote for {key} on line {number}.")
            value = "".join(result)
        else:
            value = re.split(r"\s+#", raw, maxsplit=1)[0].strip()
            if value.startswith("#"):
                value = ""
        if "\0" in value:
            raise BootstrapError(f"NUL is not allowed in {key}.")
        values[key] = value
    return values


def load_mapping():
    return json.loads((Path(__file__).with_name("github-settings.json")).read_text(encoding="utf-8"))


def placeholder(value):
    return bool(re.search(r"<[^>]*>|\b(?:todo|change[_ -]?me|dummy|replace[_ -](?:with|me))\b|replace_with|your[_ -](?:tenant|subscription|client|secret)", value, re.I))


def require_uuid(value, name):
    try:
        parsed = uuid.UUID(value)
        if parsed.int == 0:
            raise ValueError()
    except (ValueError, AttributeError):
        raise BootstrapError(f"{name} must be a nonzero UUID.") from None


def resolve_value(values, sources, environment):
    if isinstance(sources, str):
        sources = [sources]
    for source in sources:
        source = source.replace("{ENV}", environment.upper())
        if source in values:
            return values[source], source
    return "", sources[0].replace("{ENV}", environment.upper())


def validate_credentials(value, environment, tenant, subscription):
    try:
        credentials = json.loads(value)
        for key in ("clientId", "clientSecret", "tenantId", "subscriptionId"):
            if not isinstance(credentials[key], str) or not credentials[key].strip() or placeholder(credentials[key]):
                raise ValueError()
        for key in ("clientId", "tenantId", "subscriptionId"):
            require_uuid(credentials[key], key)
        if tenant and credentials["tenantId"].lower() != tenant.lower():
            raise ValueError()
        if subscription and credentials["subscriptionId"].lower() != subscription.lower():
            raise ValueError()
    except (ValueError, KeyError, TypeError, BootstrapError):
        raise BootstrapError(f"{environment}: AZURE_CREDENTIALS must contain real clientId/clientSecret/tenantId/subscriptionId matching this environment.") from None


def build_plan(values, environments, auth_mode, initial=True):
    mapping = load_mapping()
    if not environments or len(set(environments)) != len(environments) or any(env not in ENVIRONMENTS for env in environments):
        raise BootstrapError("Select distinct environments from dev,stage,prod.")
    if auth_mode not in ("oidc", "credentials"):
        raise BootstrapError("Select oidc or credentials authentication.")
    plan = {}
    for environment in environments:
        settings = {"variables": {}, "secrets": {}}
        for kind in ("variables", "secrets"):
            definitions = dict(mapping[kind])
            definitions.update({key: {"source": [f"{{ENV}}_{key}", key]}
                                for key in mapping.get("optional_" + kind, [])})
            for name, definition in definitions.items():
                if definition.get("auth") and definition["auth"] != auth_mode:
                    continue
                if "derived" in definition:
                    value = {"environment": ENVIRONMENTS[environment], "auth_mode": auth_mode}[definition["derived"]]
                    source = name
                else:
                    value, source = resolve_value(values, definition.get("source", name), environment)
                required = definition.get("required", False) and (initial or kind != "secrets")
                if not value.strip() or placeholder(value):
                    if required:
                        raise BootstrapError(f"{environment}: provide a non-placeholder value for {source}.")
                    if name == "AZURE_CREDENTIALS" and value.strip():
                        raise BootstrapError(f"{environment}: refusing placeholder AZURE_CREDENTIALS.")
                    continue
                if definition.get("managed_externally"):
                    raise BootstrapError(f"{name} is repository-scoped and managed separately; bootstrap supports GitHub dev/stage/prod only.")
                if definition.get("format") == "uuid":
                    require_uuid(value, source)
                settings[kind][name] = value
        variables, secrets = settings["variables"], settings["secrets"]
        if "AZURE_CREDENTIALS" in secrets:
            validate_credentials(secrets["AZURE_CREDENTIALS"], environment, secrets.get("TENANT_ID"),
                                 variables.get("AZURE_SUBSCRIPTION_ID"))
        plan[environment] = settings
    return plan


class Runner:
    def require_tools(self, names):
        for name in names:
            if shutil.which(name) is None:
                raise BootstrapError(f"Required tool is missing: {name}.")

    def run(self, args, input_text=None, cwd=None):
        environment = os.environ.copy()
        environment.update(GIT_TERMINAL_PROMPT="0", GH_PROMPT_DISABLED="1", GH_HOST="github.com", GCM_INTERACTIVE="Never")
        environment.pop("GH_DEBUG", None)
        try:
            result = subprocess.run(args, input=input_text, cwd=cwd, env=environment,
                                    text=True, encoding="utf-8", errors="replace",
                                    stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
        except OSError:
            raise BootstrapError(f"{args[0]} could not start; command details redacted.") from None
        if result.returncode:
            raise BootstrapError(f"{args[0]} failed (exit {result.returncode}); output redacted. Check authentication, SAML authorization and permissions.") from None
        return result.stdout


def api(runner, endpoint, method=None, payload=None, paginate=False):
    args = ["gh", "api", endpoint]
    if method:
        args += ["--method", method]
    if paginate:
        args += ["--paginate", "--slurp"]
    if payload is not None:
        args += ["--input", "-"]
    result = runner.run(args, input_text=json.dumps(payload) if payload is not None else None)
    if not result.strip():
        return {}
    try:
        return json.loads(result)
    except (ValueError, TypeError):
        raise BootstrapError("GitHub returned an invalid response; no absence inferred.") from None


def names_from_pages(result, key):
    pages = result if isinstance(result, list) else [result]
    if not pages:
        raise BootstrapError(f"GitHub returned an ambiguous empty {key} response.")
    names = set()
    for page in pages:
        if not isinstance(page, dict) or not isinstance(page.get(key), list):
            raise BootstrapError(f"GitHub returned an ambiguous {key} response.")
        for item in page[key]:
            if not isinstance(item, dict) or not isinstance(item.get("name"), str):
                raise BootstrapError(f"GitHub returned an invalid {key} item.")
            names.add(item["name"])
    return names


def repository_name(value):
    value = re.sub(r"\.git$", "", value or "", flags=re.I)
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9-]*/[A-Za-z0-9_.-]+", value or "") or value.split("/")[-1] in (".", ".."):
        raise BootstrapError("Repositories must be explicit GitHub owner/name identifiers, not URLs or local paths.")
    return value


def repository_url(name, transport):
    return f"git@github.com:{name}.git" if transport == "ssh" else f"https://github.com/{name}.git"


def check_repository(runner, name, admin=False, visibility=None):
    repo = api(runner, f"repos/{name}")
    if not isinstance(repo, dict) or repo.get("full_name", "").lower() != name.lower():
        raise BootstrapError("Repository identity could not be verified; redirects/renames are not accepted.")
    permissions = repo.get("permissions", {})
    if not isinstance(permissions, dict) or permissions.get("admin" if admin else "pull") is not True:
        raise BootstrapError("Required repository administration/read permission is not confirmed.")
    if admin and permissions.get("push") is not True:
        raise BootstrapError("Destination write permission is not confirmed.")
    if visibility and repo.get("visibility") != visibility:
        raise BootstrapError("Destination visibility does not match the explicit policy.")
    if admin and (repo.get("archived") or repo.get("disabled")):
        raise BootstrapError("Destination is archived or disabled; no writes are permitted.")
    return repo


def source_branch_exists(runner, url, branch):
    runner.run(["git", "check-ref-format", f"refs/heads/{branch}"])
    output = runner.run(["git", "ls-remote", "--exit-code", "--heads", url, f"refs/heads/{branch}"])
    if not any(line.split()[-1:] == [f"refs/heads/{branch}"] for line in output.splitlines()):
        raise BootstrapError("The selected source branch does not exist.")


def assert_empty(runner, destination):
    if runner.run(["git", "ls-remote", destination]).strip():
        raise BootstrapError("Destination has refs; mirror push refused. No destination refs were changed.")


def remove_owned_readonly(function, path, exception):
    os.chmod(path, stat.S_IWRITE | stat.S_IREAD)
    function(path)


def mirror_git(runner, source, destination, branch, workspace):
    """Only call after API authorization; repeat emptiness immediately before push."""
    if str(source).casefold() == str(destination).casefold():
        raise BootstrapError("Source and destination must differ.")
    assert_empty(runner, destination)
    source_branch_exists(runner, source, branch)
    # tempfile chooses an exclusive new child of our workspace, never ../temp.
    with tempfile.TemporaryDirectory(prefix=".bootstrap-mirror-", dir=workspace) as directory:
        mirror = Path(directory) / "mirror.git"
        try:
            runner.run(["git", "clone", "--mirror", source, str(mirror)])
            runner.run(["git", "--git-dir", str(mirror), "show-ref", "--verify", f"refs/heads/{branch}"])
            assert_empty(runner, destination)
            runner.run(["git", "--git-dir", str(mirror), "push", "--mirror", "--atomic", destination])
        finally:
            # Git objects can be read-only on Windows. Delete only our own clone.
            if mirror.exists():
                shutil.rmtree(mirror, onerror=remove_owned_readonly)


def preflight_settings(runner, destination, plan, initial):
    repo_variables = api(runner, f"repos/{destination}/actions/variables", paginate=True)
    names_from_pages(repo_variables, "variables")
    for page in repo_variables if isinstance(repo_variables, list) else [repo_variables]:
        for variable in page["variables"]:
            if variable["name"] == "AIFACTORY_GITHUB_ENVIRONMENTS":
                try:
                    routing = json.loads(variable["value"])
                    if not isinstance(routing, dict) or any(routing.get(env) != env for env in plan):
                        raise ValueError()
                except (KeyError, TypeError, ValueError):
                    raise BootstrapError("Repository environment routing does not match the selected dev/stage/prod environments.") from None
    existing = names_from_pages(api(runner, f"repos/{destination}/environments", paginate=True), "environments")
    mapping = load_mapping()
    for environment, settings in plan.items():
        if environment not in existing:
            if not initial:
                for name, definition in mapping["secrets"].items():
                    if definition.get("required") and (not definition.get("auth") or definition["auth"] == settings["variables"]["AZURE_AUTH_MODE"]):
                        if name not in settings["secrets"]:
                            raise BootstrapError(f"{environment}: new environment requires {name}.")
            continue
        endpoint = f"repos/{destination}/environments/{environment}"
        secrets = names_from_pages(api(runner, endpoint + "/secrets", paginate=True), "secrets")
        names_from_pages(api(runner, endpoint + "/variables", paginate=True), "variables")
        for name, definition in mapping["secrets"].items():
            if definition.get("required") and (not definition.get("auth") or definition["auth"] == settings["variables"]["AZURE_AUTH_MODE"]):
                if name not in settings["secrets"] and name not in secrets:
                    raise BootstrapError(f"{environment}: required secret {name} was neither supplied nor found on GitHub.")
    return existing


def sync_settings(runner, destination, plan, existing, completed):
    for environment, settings in plan.items():
        if environment not in existing:
            api(runner, f"repos/{destination}/environments/{environment}", "PUT", {})
            completed.append(f"environment {environment} created")
        for kind, command in (("variables", "variable"), ("secrets", "secret")):
            for name, value in settings[kind].items():
                runner.run(["gh", command, "set", name, "--repo", destination, "--env", environment],
                           input_text=value)
                completed.append(f"{environment} {command} {name} set")


def resolve_options(options, values):
    resolved = argparse.Namespace(**vars(options))
    fields = {
        "destination": ("GITHUB_DESTINATION_REPO", "GITHUB_NEW_REPO"),
        "environments": ("GITHUB_ENVIRONMENTS",),
        "auth_mode": ("GITHUB_AUTH_MODE",),
    }
    if options.command == "mirror":
        fields.update({
            "source": ("GITHUB_SOURCE_REPO", "GITHUB_TEMPLATE_REPO"),
            "source_branch": ("GITHUB_SOURCE_BRANCH",),
            "visibility": ("GITHUB_VISIBILITY", "GITHUB_NEW_REPO_VISIBILITY"),
            "destination_state": ("GITHUB_DESTINATION_STATE",),
            "default_branch": ("GITHUB_DEFAULT_BRANCH",),
            "transport": ("GITHUB_TRANSPORT", "GITHUB_USE_SSH"),
        })
    defaults = {"environments": "dev", "auth_mode": "oidc", "default_branch": "release/v1.25"}
    choices = {"auth_mode": ("oidc", "credentials"), "visibility": ("private", "public", "internal"),
               "destination_state": ("create", "existing-empty"), "transport": ("https", "ssh")}
    for field, keys in fields.items():
        value = getattr(options, field)
        if value is None:
            candidates = []
            for key in keys:
                if key not in values:
                    continue
                candidate = values[key]
                if key == "GITHUB_USE_SSH":
                    if candidate.lower() not in ("true", "false"):
                        raise BootstrapError("GITHUB_USE_SSH must be true or false, or use explicit --transport.")
                    candidate = "ssh" if candidate.lower() == "true" else "https"
                candidates.append(candidate)
            if len(set(candidates)) > 1:
                raise BootstrapError(f"Conflicting local policy aliases: {', '.join(keys)}. Remove the ambiguity or pass --{field.replace('_', '-')}.")
            value = candidates[0] if candidates else defaults.get(field, "")
        if not value.strip() or placeholder(value):
            raise BootstrapError(f"Configure {keys[0]} in the local .env or pass --{field.replace('_', '-')} explicitly.")
        if field in choices and value not in choices[field]:
            raise BootstrapError(f"{keys[0]} / --{field.replace('_', '-')} must be one of: {', '.join(choices[field])}.")
        setattr(resolved, field, value)
    return resolved


def execute(options, values, runner=None):
    options = resolve_options(options, values)
    runner = runner or Runner()
    destination = repository_name(options.destination)
    environments = options.environments.split(",")
    plan = build_plan(values, environments, options.auth_mode, initial=options.command == "mirror")
    source = None
    if options.command == "mirror":
        source = repository_name(options.source)
        if source.casefold() == destination.casefold():
            raise BootstrapError("Source and destination repositories must differ (case-insensitive).")
        if options.default_branch != options.source_branch:
            raise BootstrapError("Destination default branch must be the explicitly selected source release branch; no branch is rewritten.")
    completed = []
    try:
        runner.require_tools(["gh", "git"] if source else ["gh"])
        runner.run(["gh", "auth", "status", "--hostname", "github.com"])
        user = api(runner, "user")
        if not isinstance(user, dict) or not user.get("login"):
            raise BootstrapError("GitHub identity is not confirmed.")
        existing = set()
        if source:
            check_repository(runner, source)
            source_url = repository_url(source, options.transport)
            destination_url = repository_url(destination, options.transport)
            source_branch_exists(runner, source_url, options.source_branch)
            if options.destination_state == "create":
                owner = destination.split("/")[0]
                if owner.casefold() != user["login"].casefold():
                    membership = api(runner, f"orgs/{owner}/memberships/{quote(user['login'], safe='')}")
                    if not isinstance(membership, dict) or membership.get("state") != "active" or membership.get("role") != "admin":
                        raise BootstrapError("Organization owner permission is required for conservative creation preflight.")
            else:
                check_repository(runner, destination, admin=True, visibility=options.visibility)
                assert_empty(runner, destination_url)
                existing = preflight_settings(runner, destination, plan, initial=True)
        else:
            check_repository(runner, destination, admin=True)
            existing = preflight_settings(runner, destination, plan, initial=False)
        if options.dry_run:
            print("DRY RUN: read-only preflight passed. No files or GitHub settings changed.")
            if source:
                print(f"Would {options.destination_state}: {source} -> {destination}; full refs/history; destination default {options.default_branch}.")
                if options.destination_state == "create":
                    print("Creation and post-creation emptiness/permissions remain unverified until apply; a 404 is never absence proof.")
            for environment, settings in plan.items():
                for kind, entries in settings.items():
                    print(f"{environment} {kind}: " + ", ".join(sorted(entries)) + " (all values redacted)")
            return plan
        if source:
            if options.destination_state == "create":
                runner.run(["gh", "repo", "create", destination, "--" + options.visibility])
                completed.append("destination repository created")
                check_repository(runner, destination, admin=True, visibility=options.visibility)
                existing = preflight_settings(runner, destination, plan, initial=True)
            # Recheck both API permissions and refs after creation/preflight.
            check_repository(runner, destination, admin=True, visibility=options.visibility)
            mirror_git(runner, source_url, destination_url, options.source_branch, ROOT)
            completed.append("full Git mirror pushed")
            api(runner, f"repos/{destination}", "PATCH", {"default_branch": options.default_branch})
            verified = check_repository(runner, destination, admin=True, visibility=options.visibility)
            if verified.get("default_branch") != options.default_branch:
                raise BootstrapError("Destination default branch update could not be verified.")
            completed.append("destination default branch selected")
        sync_settings(runner, destination, plan, existing, completed)
    except (BootstrapError, OSError) as error:
        summary = "; ".join(completed) if completed else "none"
        if not isinstance(error, BootstrapError):
            error = "Local filesystem operation failed; details redacted."
        raise BootstrapError(f"{error}\nCompleted: {summary}. No automatic rollback or deletion is attempted; a failed write may have reached GitHub. Inspect the destination before retrying.") from None
    print(f"Completed {options.command}: {destination}; environments: {', '.join(environments)}. Values redacted.")
    return plan


def parser():
    result = argparse.ArgumentParser(description=__doc__)
    commands = result.add_subparsers(dest="command", required=True)
    for name in ("mirror", "sync"):
        command = commands.add_parser(name)
        command.add_argument("--env-file", type=Path, default=ROOT / ".env", help="Defaults to repository-root .env; explicit relative paths use caller cwd; never sourced")
        command.add_argument("--destination", help="Override GITHUB_DESTINATION_REPO (GitHub owner/repository)")
        command.add_argument("--environments", help="Override GITHUB_ENVIRONMENTS (default dev); comma-separated dev,stage,prod")
        command.add_argument("--auth-mode", choices=("oidc", "credentials"), help="Override GITHUB_AUTH_MODE (default oidc)")
        command.add_argument("--dry-run", action="store_true", help="Read-only preflight and redacted plan; no writes, clone or push")
        if name == "mirror":
            command.add_argument("--source", help="Override GITHUB_SOURCE_REPO (GitHub owner/repository)")
            command.add_argument("--source-branch", help="Override GITHUB_SOURCE_BRANCH")
            command.add_argument("--visibility", choices=("private", "public", "internal"), help="Override GITHUB_VISIBILITY")
            command.add_argument("--destination-state", choices=("create", "existing-empty"), help="Override GITHUB_DESTINATION_STATE; explicit intent is mandatory")
            command.add_argument("--default-branch", help="Override GITHUB_DEFAULT_BRANCH (default release/v1.25); destination only, must match source-branch")
            command.add_argument("--transport", choices=("https", "ssh"), help="Override GITHUB_TRANSPORT")
    return result


def main(argv=None):
    options = parser().parse_args(argv)
    try:
        execute(options, parse_env(options.env_file))
    except BootstrapError as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
