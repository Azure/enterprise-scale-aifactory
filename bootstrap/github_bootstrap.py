"""Fail-closed v1.25+ GitHub mirror/settings bootstrap; not registered factory configuration."""

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
ENVIRONMENTS = ("dev", "stage", "prod")
POLICY_FIELDS = {
    "destination": ("GITHUB_DESTINATION_REPO", "GITHUB_NEW_REPO"),
    "environments": ("GITHUB_ENVIRONMENTS",),
    "auth_mode": ("GITHUB_AUTH_MODE",),
    "source": ("GITHUB_SOURCE_REPO", "GITHUB_TEMPLATE_REPO"),
    "source_branch": ("GITHUB_SOURCE_BRANCH",),
    "visibility": ("GITHUB_VISIBILITY", "GITHUB_NEW_REPO_VISIBILITY"),
    "destination_state": ("GITHUB_DESTINATION_STATE",),
    "default_branch": ("GITHUB_DEFAULT_BRANCH",),
    "transport": ("GITHUB_TRANSPORT", "GITHUB_USE_SSH"),
}


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


def validate_keys(values, mapping):
    allowed = {key for keys in POLICY_FIELDS.values() for key in keys}
    sources = [mapping["environment_source"]]
    for kind in ("variables", "secrets"):
        for definition in mapping[kind].values():
            source = definition["source"]
            sources.extend([source] if isinstance(source, str) else source)
    allowed.update(source.replace("{ENV}", env.upper()) for source in sources for env in ENVIRONMENTS)
    unknown = sorted(set(values) - allowed)
    if unknown:
        raise BootstrapError("Unsupported .env keys: " + ", ".join(unknown)
                             + ". Use the registered API for factory configuration; this helper only manages GitHub authentication settings.")


def build_plan(values, environments, auth_mode, initial=True):
    mapping = load_mapping()
    validate_keys(values, mapping)
    if not environments or len(set(environments)) != len(environments) or any(env not in ENVIRONMENTS for env in environments):
        raise BootstrapError("Select distinct environments from dev,stage,prod.")
    if auth_mode not in mapping["auth_modes"]:
        raise BootstrapError("Select an explicit supported OIDC mode; the pinned lifecycle templates do not support AZURE_CREDENTIALS.")
    plan = {}
    for environment in environments:
        source = mapping["environment_source"].replace("{ENV}", environment.upper())
        namespace = values.get(source, environment)
        if not re.fullmatch(r"[A-Za-z0-9_.-]{1,128}", namespace) or placeholder(namespace):
            raise BootstrapError(f"{source} must name the exact reviewed provider auth_namespace (1-128 letters, digits, dot, underscore or hyphen).")
        if namespace.casefold() in {name.casefold() for name in plan}:
            raise BootstrapError("Selected environments must have distinct GitHub auth namespaces.")
        settings = {"variables": {}, "secrets": {}}
        for kind in ("variables", "secrets"):
            for name, definition in mapping[kind].items():
                if definition.get("auth") and definition["auth"] != auth_mode:
                    continue
                value, source = resolve_value(values, definition["source"], environment)
                required = definition.get("required", False) and initial
                if not value.strip() or placeholder(value):
                    if required:
                        raise BootstrapError(f"{environment}: provide a non-placeholder value for {source}.")
                    continue
                if definition.get("format") == "uuid":
                    require_uuid(value, source)
                settings[kind][name] = value
        plan[namespace] = settings
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
    require_registered_release(branch)
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
    require_registered_release(branch)
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


def preflight_settings(runner, destination, plan, auth_mode):
    repo_variables = api(runner, f"repos/{destination}/actions/variables", paginate=True)
    names_from_pages(repo_variables, "variables")
    existing = names_from_pages(api(runner, f"repos/{destination}/environments", paginate=True), "environments")
    mapping = load_mapping()
    for environment, settings in plan.items():
        if environment not in existing and environment.casefold() in {name.casefold() for name in existing}:
            raise BootstrapError("Use the existing GitHub environment's exact spelling; no environment protection is changed.")
        for kind in ("variables", "secrets"):
            names, remote = set(), {}
            if environment in existing:
                endpoint = f"repos/{destination}/environments/{environment}/{kind}"
                response = api(runner, endpoint, paginate=True)
                names = names_from_pages(response, kind)
                if kind == "variables":
                    remote = {item["name"]: item.get("value") for page in (
                        response if isinstance(response, list) else [response]) for item in page[kind]}
            for name, definition in mapping[kind].items():
                if not definition.get("required") or definition.get("auth", auth_mode) != auth_mode:
                    continue
                if name in settings[kind]:
                    continue
                if name not in names:
                    raise BootstrapError(f"{environment}: required {kind} {name} was neither supplied nor found on GitHub.")
                if kind == "variables":
                    value = remote[name]
                    if not isinstance(value, str) or not value.strip() or placeholder(value):
                        raise BootstrapError(f"{environment}: existing variable {name} is not valid.")
                    if definition.get("format") == "uuid":
                        require_uuid(value, name)
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
    fields = {field: keys for field, keys in POLICY_FIELDS.items()
              if options.command == "mirror" or field in ("destination", "environments", "auth_mode")}
    defaults = {"environments": "dev"}
    choices = {"auth_mode": tuple(load_mapping()["auth_modes"]), "visibility": ("private", "public", "internal"),
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
            value = candidates[0] if candidates else (
                resolved.source_branch if field == "default_branch" else defaults.get(field, ""))
        if not value.strip() or placeholder(value):
            raise BootstrapError(f"Configure {keys[0]} in the local .env or pass --{field.replace('_', '-')} explicitly.")
        if field in choices and value not in choices[field]:
            raise BootstrapError(f"{keys[0]} / --{field.replace('_', '-')} must be one of: {', '.join(choices[field])}.")
        setattr(resolved, field, value)
    return resolved


def require_registered_release(branch):
    version = re.fullmatch(r"release/v([1-9][0-9]*)\.(0|[1-9][0-9]*)(?:\.(0|[1-9][0-9]*))?", branch)
    if not version or tuple(int(part) for part in version.groups()[:2]) < (1, 25):
        raise BootstrapError("Select an explicit release/v1.25 or later source branch; legacy releases and main are not supported.")


def execute(options, values, runner=None):
    options = resolve_options(options, values)
    runner = runner or Runner()
    destination = repository_name(options.destination)
    environments = options.environments.split(",")
    plan = build_plan(values, environments, options.auth_mode, initial=options.command == "mirror")
    source = None
    if options.command == "mirror":
        require_registered_release(options.source_branch)
        source = repository_name(options.source)
        if source.casefold() == destination.casefold():
            raise BootstrapError("Source and destination repositories must differ (case-insensitive).")
        if options.default_branch != options.source_branch:
            raise BootstrapError("Destination default branch must be the explicitly selected source release branch; no branch is rewritten.")
        if options.auth_mode == "oidc-single-writer" and options.visibility != "private":
            raise BootstrapError("The pinned single-writer contract requires a private destination repository.")
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
                existing = preflight_settings(runner, destination, plan, options.auth_mode)
        else:
            check_repository(runner, destination, admin=True,
                             visibility="private" if options.auth_mode == "oidc-single-writer" else None)
            existing = preflight_settings(runner, destination, plan, options.auth_mode)
        if options.dry_run:
            print("DRY RUN: read-only preflight passed. No files or GitHub settings changed.")
            print("Settings target GitHub environments only; no register, API/runtime configuration, workflow, federation or pipeline binding is created or verified.")
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
                existing = preflight_settings(runner, destination, plan, options.auth_mode)
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
    print("GitHub settings only: registered catalog, API/runtime, federation and pipeline bindings remain unchanged and unverified.")
    return plan


def parser():
    result = argparse.ArgumentParser(description=__doc__)
    commands = result.add_subparsers(dest="command", required=True)
    for name in ("mirror", "sync"):
        command = commands.add_parser(name)
        command.add_argument("--env-file", type=Path, default=ROOT / ".env", help="Defaults to repository-root .env; explicit relative paths use caller cwd; never sourced")
        command.add_argument("--destination", help="Override GITHUB_DESTINATION_REPO (GitHub owner/repository)")
        command.add_argument("--environments", help="Override GITHUB_ENVIRONMENTS (default dev); comma-separated dev,stage,prod")
        command.add_argument("--auth-mode", choices=tuple(load_mapping()["auth_modes"]),
                             help="Required explicit workflow authentication contract; no credential-JSON fallback is supported by the pinned templates")
        command.add_argument("--dry-run", action="store_true", help="Read-only preflight and redacted plan; no writes, clone or push")
        if name == "mirror":
            command.add_argument("--source", help="Override GITHUB_SOURCE_REPO (GitHub owner/repository)")
            command.add_argument("--source-branch", help="Override GITHUB_SOURCE_BRANCH")
            command.add_argument("--visibility", choices=("private", "public", "internal"), help="Override GITHUB_VISIBILITY")
            command.add_argument("--destination-state", choices=("create", "existing-empty"), help="Override GITHUB_DESTINATION_STATE; explicit intent is mandatory")
            command.add_argument("--default-branch", help="Override GITHUB_DEFAULT_BRANCH (defaults to selected source branch); destination only, must match source-branch")
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
