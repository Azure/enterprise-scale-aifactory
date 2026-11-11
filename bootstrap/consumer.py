"""Pinned BLUE consumer adapter; shared bootstrap implementation stays in PURPLE."""

import argparse
from datetime import datetime, timezone
import importlib.util
import json
import os
from pathlib import Path
import re
import shlex
import shutil
import subprocess
import sys
from uuid import uuid4

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]
SUBMODULE = "azure-enterprise-scale-ml"
PIN = "89eca66185366a702b026cec8c938570548c649c"
BRANCH = "release/v1.25"
SOURCE_URL = "https://github.com/jostrm/azure-enterprise-scale-ml"
LEGACY_BASELINE = "9926d705"
SETTINGS = Path("environment_setup/aifactory/bicep/copy_to_local_settings")
ADO = Path("aifactory/esml-infra/azure-devops/bicep/yaml")
WORKFLOWS = (
    "infra-common.yml", "infra-project.yml", "infra-project-phase.yml",
    "infra-ai-gateway.yml", "infra-project-dashboards.yml", "infra-project-healthmodel.yml",
)
OBSOLETE_WORKFLOWS = (
    "infra-project-esml.yml", "infra-project-genai.yml",
    "infra-add-core-member.yml", "infra-add-project-member.yml",
)
OIDC_CONDITION = "(vars.AZURE_AUTH_MODE == 'oidc' || (vars.AZURE_AUTH_MODE == '' && env.AZURE_CLIENT_ID != ''))"
CREDENTIALS_CONDITION = "(vars.AZURE_AUTH_MODE == 'credentials' || (vars.AZURE_AUTH_MODE == '' && env.AZURE_CLIENT_ID == ''))"
GATEWAY_LOGIN_GATE = "env.ENABLE_APIM != 'true' || env.APIM_GATEWAY_MANAGED_PROVISIONING != 'true' || inputs.action != 'plan'"
ENTRY_POINTS = {
    "cli": "environment_setup/azurefactory-cli/src/azurefactory/__main__.py",
    "sdk": "environment_setup/azurefactory-cli/src/azurefactory/client.py",
    "api_distribution": "environment_setup/install_config_wizard/release-manifest.json",
    "api_examples": "environment_setup/install_config_wizard/api-usage-examples",
    "agent_factory": "usecase_code/40-agent-factory",
    "ml_factory": "usecase_code/50-ml-model-factory",
    "governance": str(SETTINGS / "azure-devops/esml-yaml-pipelines/aifactory-governance"),
    "registered_initializer": "01-start-v125-and-above.sh",
}


def git(root, *args, required=True):
    result = subprocess.run(
        ["git", "-C", str(root), *args], capture_output=True, check=False,
        env={**os.environ, "GIT_TERMINAL_PROMPT": "0", "GCM_INTERACTIVE": "Never", "GIT_OPTIONAL_LOCKS": "0"},
    )
    if result.returncode and required:
        raise ValueError(f"Git failed ({' '.join(args[:2])}); verify the consumer repository and selected gitlink.")
    return result.stdout if result.returncode == 0 else b""


def module_metadata(root):
    path = root / ".gitmodules"
    if path.is_symlink() or (hasattr(path, "is_junction") and path.is_junction()):
        raise ValueError(".gitmodules must not be a symlink or junction.")
    if path.exists() and not path.is_file():
        raise ValueError(".gitmodules must be an ordinary file.")
    if path.exists():
        git(root, "config", "--file", str(path), "--list")
    return {key: git(root, "config", "--file", str(path), "--get",
                     f"submodule.{SUBMODULE}.{key}", required=False).decode().strip()
            for key in ("path", "url", "branch")}


def repair_submodule(root, *, expected=PIN, url=SOURCE_URL, dry_run=False):
    """Explicit local repair for template services that omit gitlinks; never adopt populated paths."""
    root = Path(root).absolute()
    if not (root / ".git").exists():
        raise ValueError("Repair requires an existing consumer Git repository.")
    top = Path(git(root, "rev-parse", "--show-toplevel").decode().strip())
    if top.resolve() != root.resolve():
        raise ValueError("Select the consumer Git repository root for repair.")
    for path in (root, *root.parents):
        if path.is_symlink() or (hasattr(path, "is_junction") and path.is_junction()):
            raise ValueError("Repair cannot traverse symlinks or junctions.")
    entry = git(root, "ls-files", "--stage", "--", SUBMODULE).decode().split()
    if entry and (len(entry) != 4 or entry[0] != "160000" or entry[1] != expected or entry[2] != "0"):
        raise ValueError("Repair will not replace existing tracked files or a different gitlink pin.")
    source = root / SUBMODULE
    if source.is_symlink() or (hasattr(source, "is_junction") and source.is_junction()):
        raise ValueError("Repair refuses a linked submodule path.")
    if source.exists():
        if not source.is_dir():
            raise ValueError("Repair refuses a populated/non-directory submodule path.")
        if not entry and any(source.iterdir()):
            raise ValueError("Repair refuses a populated untracked submodule path; preserve/move it aside manually.")
        if (source / ".git").exists():
            if git(source, "rev-parse", "HEAD").decode().strip() != expected or git(
                    source, "status", "--porcelain", "--untracked-files=all"):
                raise ValueError("Repair refuses an initialized source with a different pin or local modifications.")
        elif any(source.iterdir()):
            raise ValueError("Repair refuses populated source files without submodule metadata.")
    metadata = module_metadata(root)
    if metadata["path"] not in ("", SUBMODULE) or metadata["branch"] not in ("", BRANCH):
        raise ValueError("Existing submodule metadata conflicts with the selected release; review it manually.")
    registrations = git(root, "config", "--file", str(root / ".gitmodules"), "--get-regexp",
                        r"^submodule\..*\.path$", required=False).decode().splitlines()
    for registration in registrations:
        key, value = registration.split(None, 1)
        if value == SUBMODULE and key != f"submodule.{SUBMODULE}.path":
            raise ValueError("Another submodule registration already owns this path; review it manually.")
    if dry_run:
        print(f"Would repair missing .gitmodules metadata and gitlink {expected}; no files or index entries changed.")
        return
    for key, value in (("path", SUBMODULE), ("url", metadata["url"] or url), ("branch", BRANCH)):
        if not metadata[key]:
            git(root, "config", "--file", str(root / ".gitmodules"), f"submodule.{SUBMODULE}.{key}", value)
    if not entry:
        git(root, "update-index", "--add", "--cacheinfo", f"160000,{expected},{SUBMODULE}")
    print("Local submodule registration repaired; gitlink staged. Review/stage .gitmodules; nothing committed.")


def ensure_submodule(root, *, expected=PIN, dry_run=False):
    """Initialize the recorded gitlink only; never select a remote branch tip."""
    root = Path(root).absolute()
    metadata = module_metadata(root)
    if metadata["path"] != SUBMODULE or not metadata["url"]:
        raise ValueError("Missing .gitmodules registration; use 01b --repair-submodule explicitly.")
    entry = git(root, "ls-files", "--stage", "--", SUBMODULE).decode().split()
    if len(entry) != 4 or entry[0] != "160000" or entry[1] != expected or entry[2] != "0":
        raise ValueError(f"The consumer gitlink must select {expected}; use --repair-submodule only if it is missing.")
    source = root / SUBMODULE
    if source.is_symlink() or (hasattr(source, "is_junction") and source.is_junction()):
        raise ValueError("The source submodule must not be a symlink or junction.")
    if (source / ".git").exists():
        if git(source, "status", "--porcelain", "--untracked-files=all"):
            raise ValueError("The source submodule is dirty/modified; preserve those edits before continuing.")
        if git(source, "rev-parse", "HEAD").decode().strip() != expected:
            raise ValueError("The initialized submodule differs from the selected pin; no checkout was performed.")
        return source
    if dry_run:
        print(f"Would initialize {SUBMODULE} at recorded gitlink {expected}; no files changed.")
        return None
    git(root, "submodule", "update", "--init", "--recursive", "--", SUBMODULE)
    if git(source, "rev-parse", "HEAD").decode().strip() != expected:
        raise ValueError("Submodule initialization did not produce the selected pin.")
    return source


def load_upstream(source):
    library = source / "bootstrap/lib"
    for name in ("initialize_azurefactory", "bootstrap_no_delete"):
        path = library / (name + ".py")
        if not path.is_file():
            raise ValueError(f"Missing immutable upstream bootstrap helper: {path}")
        spec = importlib.util.spec_from_file_location(name, path)
        module = importlib.util.module_from_spec(spec)
        sys.modules[name] = module
        spec.loader.exec_module(module)
    return sys.modules["bootstrap_no_delete"]


def normalized(data):
    return data.replace(b"\r\n", b"\n")


def legacy_bytes(root, relative):
    return git(root, "show", f"{LEGACY_BASELINE}:{Path(relative).as_posix()}", required=False)


def is_legacy(root, path):
    relative = path.relative_to(root)
    exists = git(root, "ls-tree", "--full-tree", LEGACY_BASELINE, "--", relative.as_posix(), required=False)
    original = legacy_bytes(root, relative)
    return bool(exists) and normalized(path.read_bytes()) == normalized(original)


def release_json(source):
    payload = json.loads((source / "environment_setup/aifactory/variables.json").read_text(encoding="utf-8-sig"))
    for section in payload.values():
        if isinstance(section, dict):
            for key, value in (("aifactory_version_major", "1"), ("aifactory_version_minor", "25"),
                               ("aifactory_branch_chosen", BRANCH)):
                if key in section:
                    section[key] = value
    return (json.dumps(payload, indent=2, ensure_ascii=False) + "\n").encode()


def release_yaml(source):
    text = (source / SETTINGS / "azure-devops/esml-yaml-pipelines/variables/variables.yaml").read_text(
        encoding="utf-8-sig")
    for key, value in (("aifactory_version_major", "1"), ("aifactory_version_minor", "25"),
                       ("aifactory_branch_chosen", BRANCH)):
        text, count = re.subn(
            rf'(?m)^  {key}:.*$', f'  {key}: "{value}" # BLUE selected source release', text)
        if count != 1:
            raise ValueError(f"Upstream YAML release metadata contract changed: {key}")
    return text.encode()


def auth_guard(indent, json_flag="'false'"):
    lines = [
        "- name: Validate BLUE authentication selection",
        "  shell: pwsh",
        "  env:",
        "    BLUE_AUTH_MODE: ${{ vars.AZURE_AUTH_MODE }}",
        "    BLUE_JSON_IDENTITY: " + json_flag,
        "  run: |",
        "    if ($env:BLUE_AUTH_MODE -notin @('', 'oidc', 'credentials')) { throw 'Unknown AZURE_AUTH_MODE' }",
        "    if ($env:BLUE_AUTH_MODE -eq 'credentials' -and $env:BLUE_JSON_IDENTITY -eq 'true') { throw 'JSON identity requires OIDC; select environment configuration for credentials mode' }",
    ]
    return "".join(indent + line + "\n" for line in lines)


def replace_contract(text, old, new, count=1):
    if text.count(old) != count:
        raise ValueError("Pinned workflow authentication contract changed; review the BLUE adapter.")
    return text.replace(old, new)


def render_workflow(path):
    """Only adapt authentication selection; preserve the pinned deployment implementation."""
    text = path.read_text(encoding="utf-8-sig")
    name = path.name
    if name in {"infra-common.yml", "infra-project-phase.yml"}:
        common = name == "infra-common.yml"
        flag = "use_json_config_override" if common else "json_identity_auth"
        first = "      - name: Azure login with OpenID Connect (OIDC)\n        if: ${{ inputs." + flag + " }}"
        text = replace_contract(text, first, auth_guard("      ", "${{ inputs." + flag + " }}") + first,
                                3 if common else 1)
        text = replace_contract(text, "env.AZURE_CLIENT_ID != ''", OIDC_CONDITION, 3 if common else 2)
        text = replace_contract(text, "env.AZURE_CLIENT_ID == ''", CREDENTIALS_CONDITION, 3 if common else 1)
    elif name in {"infra-project-dashboards.yml", "infra-project-healthmodel.yml"}:
        first = "      - name: Sign in with the existing environment OIDC identity\n"
        text = replace_contract(
            text, first, auth_guard("      ") + first + "        if: ${{ vars.AZURE_AUTH_MODE != 'credentials' }}\n")
        tail = "          subscription-id: ${{ vars.AZURE_SUBSCRIPTION_ID }}\n"
        credentials = (
            "      - name: Sign in with explicitly selected service-principal credentials\n"
            "        if: ${{ vars.AZURE_AUTH_MODE == 'credentials' }}\n"
            "        uses: azure/login@v2\n"
            "        with:\n"
            "          creds: ${{ secrets.AZURE_CREDENTIALS }}\n"
        )
        text = replace_contract(text, tail, tail + credentials)
    elif name == "infra-ai-gateway.yml":
        text = replace_contract(text, "\njobs:\n", "\npermissions:\n  contents: read\n  id-token: write\n\njobs:\n")
        original = (
            "    - name: Azure Login\n"
            f"      if: {GATEWAY_LOGIN_GATE}\n"
            "      uses: azure/login@v2\n"
            "      with:\n"
            "        creds: ${{ secrets.AZURE_CREDENTIALS }}\n"
        )
        replacement = auth_guard("    ") + (
            "    - name: Azure Login with explicitly selected OIDC\n"
            "      if: ${{ (" + GATEWAY_LOGIN_GATE + ") && vars.AZURE_AUTH_MODE == 'oidc' }}\n"
            "      uses: azure/login@v2\n"
            "      with:\n"
            "        client-id: ${{ secrets.AZURE_CLIENT_ID }}\n"
            "        tenant-id: ${{ secrets.TENANT_ID }}\n"
            "        subscription-id: ${{ vars.AZURE_SUBSCRIPTION_ID }}\n"
            "    - name: Azure Login with service-principal credentials\n"
            "      if: ${{ (" + GATEWAY_LOGIN_GATE + ") && vars.AZURE_AUTH_MODE != 'oidc' }}\n"
            "      uses: azure/login@v2\n"
            "      with:\n"
            "        creds: ${{ secrets.AZURE_CREDENTIALS }}\n"
        )
        text = replace_contract(text, original, replacement)
    else:
        return path.read_bytes()
    return ("# BLUE authentication adapter; deployment logic comes from the pinned PURPLE template.\n" + text).encode()


def build_plan(root, source, *, include_bundle=True):
    upstream = load_upstream(source)
    upstream.starter.ordinary(root)
    upstream.starter.ordinary(source)
    if not root.is_dir():
        raise ValueError("Consumer root must already exist.")
    for ancestor in (root, *root.parents):
        if (ancestor / "azurefactory").exists() or (
                ancestor.name == "azurefactory" and (ancestor / "register.json").exists()):
            raise ValueError("This adapter supports legacy aifactory only; registered azurefactory requires reviewed migration.")
    for name, relative in ENTRY_POINTS.items():
        if not (source / relative).exists():
            raise ValueError(f"Missing upstream {name} entry point: {relative}")
    merge = upstream.Merge(root)
    if include_bundle:
        upstream.bundle(merge, source / "bootstrap")
    settings = source / SETTINGS
    native_workflows = {}
    for workflow in WORKFLOWS:
        origin = settings / "github-actions" / workflow
        destination = Path(".github/workflows") / workflow
        merge.file(render_workflow(origin), destination)
        native_workflows[root / destination] = origin
    merge.tree(settings / "azure-devops/esml-yaml-pipelines", ADO)
    merge.tree(settings / "automation", Path("aifactory/automation"))
    merge.tree(settings / "ai-gateway", Path("aifactory/ai-gateway"))
    # Provider YAML is canonical; Bicep, CLI/API, Agent and ML code run from the gitlink.
    # Avoid a second stale copy of implementation under aifactory.
    for path in list(merge.files):
        if path.suffix.lower() == ".md":
            del merge.files[path]
    yaml_active = root / ADO / "variables/variables.yaml"
    merge.files.pop(yaml_active, None)
    values = release_json(source)
    yaml = release_yaml(source)
    merge.file(values, Path("aifactory/variables-template.json"))
    merge.file(values, Path("aifactory/variables.json"), preserve=True)
    merge.file(yaml, ADO / "variables/variables-template.yaml")
    if not yaml_active.exists() or is_legacy(root, yaml_active):
        merge.file(yaml, ADO / "variables/variables.yaml")
    else:
        print(f"Preserved active configuration: {yaml_active}")
    retire = []
    planned_destinations = set(merge.files)
    for destination, origin in list(merge.files.items()):
        if not destination.exists():
            continue
        wanted = origin.read_bytes() if isinstance(origin, Path) else origin
        if normalized(destination.read_bytes()) == normalized(wanted):
            if destination.read_bytes() != wanted:
                # The upstream exclusive writer cannot replace an equivalent CRLF projection.
                del merge.files[destination]
            continue
        native = native_workflows.get(destination)
        is_native = native is not None and normalized(destination.read_bytes()) == normalized(native.read_bytes())
        if not is_native and not is_legacy(root, destination):
            raise ValueError(f"Locally modified file conflicts with release template; review and move it aside: {destination}")
        if isinstance(origin, bytes):
            retire.append(destination)
    baseline_paths = git(root, "ls-tree", "--full-tree", "-r", "--name-only", LEGACY_BASELINE, "--",
                         "aifactory", ".github/workflows", required=False).decode().splitlines()
    obsolete = {root / name for name in baseline_paths if root / name not in planned_destinations}
    obsolete.update(root / ".github/workflows" / name for name in OBSOLETE_WORKFLOWS)
    for path in sorted(obsolete):
        upstream.starter.ordinary(path)
        if not path.exists():
            continue
        if path == yaml_active:
            continue
        if not path.is_file() or not is_legacy(root, path):
            raise ValueError(f"Modified legacy copy requires manual review/migration, not silent removal: {path}")
        retire.append(path)
    return merge, sorted(set(retire))


def refresh(root, source, *, dry_run=False, include_bundle=True):
    root, source = Path(root).absolute(), Path(source).absolute()
    merge, retire = build_plan(root, source, include_bundle=include_bundle)
    if dry_run:
        print(f"Plan: {len(merge.files)} upstream files; {len(retire)} unchanged obsolete baseline files to archive.")
        print("Active .env, JSON, YAML and BLUE variable-sync scripts are preserved; no files changed.")
        return
    if retire:
        backup = root / ".aifactory-backups" / (
            "legacy-" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S") + "-" + uuid4().hex)
        sys.modules["initialize_azurefactory"].ordinary(backup)
        for path in retire:
            target = backup / path.relative_to(root)
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, target)
        for path in retire:
            path.unlink()
        print(f"Archived unchanged obsolete baseline files privately: {backup}")
    print("Upstream non-deleting copy phase:")
    merge.execute()
    print(f"Consumer templates ready at {PIN} ({BRANCH}); no Azure or provider operation ran.")
    print("Review variables-template.json/YAML against active configuration; no automatic configuration merge.")


def dispatch_command(target, repository, ref, environment, *, include_common_prerequisites=False,
                     use_json_config_override=False):
    workflows = {
        "common": "infra-common.yml", "project": "infra-project.yml",
        "dashboards": "infra-project-dashboards.yml", "healthmodel": "infra-project-healthmodel.yml",
        "gateway": "infra-ai-gateway.yml",
    }
    if target not in workflows or environment not in {"dev", "stage", "prod"}:
        raise ValueError("Select a supported workflow target and dev, stage or prod.")
    if not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", repository):
        raise ValueError("An explicit GitHub repository OWNER/REPO is required.")
    if not ref or ref.startswith("-") or any(c.isspace() for c in ref):
        raise ValueError("An explicit consumer branch/ref is required; main is never assumed.")
    command = ["gh", "workflow", "run", workflows[target], "--repo", repository, "--ref", ref]
    inputs = {"environment": environment}
    if target == "common":
        if environment != "dev" and not include_common_prerequisites:
            raise ValueError("Upstream common Stage/Prod require prior environments; review --include-common-prerequisites.")
        environments = ("dev", "stage", "prod")
        inputs = {f"deploy_{name}": str(index <= environments.index(environment)).lower()
                  for index, name in enumerate(environments)}
        inputs["use_json_config_override"] = str(use_json_config_override).lower()
    if target in {"common", "project", "dashboards", "healthmodel"}:
        inputs["config_file"] = "aifactory/variables.json"
    if target in {"dashboards", "healthmodel"}:
        inputs["mode"] = "plan"
    if target == "gateway":
        inputs["action"] = "plan"
    for key, value in inputs.items():
        command.extend(["--raw-field", f"{key}={value}"])
    return command


def validate_dispatch_ref(root, source, ref, workflow):
    entry = git(root, "ls-tree", ref, "--", SUBMODULE).decode().split()
    if len(entry) != 4 or entry[0] != "160000" or entry[2] != PIN:
        raise ValueError("Selected consumer ref does not contain the approved gitlink; publish the reviewed changes first.")
    required = [workflow]
    if workflow == "infra-project.yml":
        required.append("infra-project-phase.yml")
    for name in required:
        committed = git(root, "show", f"{ref}:.github/workflows/{name}")
        canonical = render_workflow(source / SETTINGS / "github-actions" / name)
        if normalized(committed) != normalized(canonical):
            raise ValueError(f"Selected ref does not contain the pinned workflow template: {name}")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("operation", choices=("init", "refresh", "deploy"))
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--dry-run", action="store_true", help="Validate and print the local plan; never write or dispatch.")
    parser.add_argument("--repair-submodule", action="store_true",
                        help="Init only: explicitly repair missing registration/gitlink; refuse populated untracked paths.")
    parser.add_argument("--target", choices=("common", "project", "dashboards", "healthmodel", "gateway"), default="project")
    parser.add_argument("--environment", choices=("dev", "stage", "prod"), default="dev")
    parser.add_argument("--repo", default="")
    parser.add_argument("--ref", default="")
    parser.add_argument("--execute", action="store_true", help="Explicitly dispatch the selected GitHub workflow (deploy only).")
    parser.add_argument("--include-common-prerequisites", action="store_true",
                        help="Explicitly include Dev for common Stage, or Dev and Stage for common Prod.")
    parser.add_argument("--use-json-config-override", action="store_true",
                        help="Common only: select variables.json and its OIDC identity instead of GitHub Environment configuration.")
    args = parser.parse_args(argv)
    try:
        if args.execute and (args.operation != "deploy" or args.dry_run):
            raise ValueError("--execute applies only to deploy and cannot be combined with --dry-run.")
        if args.use_json_config_override and (args.operation != "deploy" or args.target != "common"):
            raise ValueError("--use-json-config-override applies only to common deployment.")
        root = args.root.absolute()
        if args.repair_submodule:
            if args.operation != "init":
                raise ValueError("--repair-submodule applies only to init (01b).")
            repair_submodule(root, dry_run=args.dry_run)
            if args.dry_run:
                return 0
        if args.operation == "deploy" and not (root / SUBMODULE / ".git").exists():
            raise ValueError("Initialize the pinned consumer before planning deployment.")
        source = ensure_submodule(root, dry_run=args.dry_run)
        if source is None:
            return 0
        if args.operation != "deploy":
            refresh(root, source, dry_run=args.dry_run)
            return 0
        ref = args.ref or git(root, "branch", "--show-current").decode().strip()
        command = dispatch_command(args.target, args.repo, ref, args.environment,
                                   include_common_prerequisites=args.include_common_prerequisites,
                                   use_json_config_override=args.use_json_config_override)
        workflow = command[3]
        if not (root / ".github/workflows" / workflow).is_file():
            raise ValueError("Selected workflow is not installed; run 03b first.")
        print(shlex.join(command))
        if args.target == "gateway":
            print("Gateway action=plan applies only to managed APIM; classic APIM/Kong may deploy when enabled.")
        if not args.execute:
            print("Plan only. Review configuration/authentication and publish this consumer ref before --execute.")
            return 0
        validate_dispatch_ref(root, source, ref, workflow)
        for arguments in (["gh", "auth", "status"], command):
            result = subprocess.run(arguments, cwd=root, check=False)
            if result.returncode:
                raise ValueError("GitHub authentication or workflow dispatch failed; no success is claimed.")
        print("Workflow dispatch accepted; deployment completion is NOT verified. Observe the GitHub run.")
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
