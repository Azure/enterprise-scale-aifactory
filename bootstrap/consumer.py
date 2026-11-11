"""Pinned BLUE adapter for v1.25+ registered consumers; never install legacy layouts."""

import argparse
import json
import os
from pathlib import Path
import stat
import subprocess
import sys

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]
SUBMODULE = "azure-enterprise-scale-ml"
PIN = "89eca66185366a702b026cec8c938570548c649c"
BRANCH = "release/v1.25"
SOURCE_URL = "https://github.com/jostrm/azure-enterprise-scale-ml"
SCOPED_GHA = Path(".github/workflows/factory-lifecycle.yml")
SCOPED_GHA_TEMPLATE = Path("bootstrap/templates/factory-lifecycle-gha.yml")
ADO_LIMITATION = (
    "ADO local registered initialization/refresh only: scoped ADO pipeline/runtime is blocked "
    "by the pinned upstream path contract. No ADO pipeline or legacy fallback is installed."
)
ENTRY_POINTS = {
    "cli": "environment_setup/azurefactory-cli/src/azurefactory/__main__.py",
    "sdk": "environment_setup/azurefactory-cli/src/azurefactory/client.py",
    "api_distribution": "environment_setup/install_config_wizard/release-manifest.json",
    "api_examples": "environment_setup/install_config_wizard/api-usage-examples",
    "agent_factory": "usecase_code/40-agent-factory",
    "ml_factory": "usecase_code/50-ml-model-factory",
    "registered_initializer": "01-start-v125-and-above.sh",
    "registered_installer": "bootstrap/lib/registered_setup.py",
}

DEPLOY_DIAGNOSTIC = """ERROR: 04ab/deploy is retired: BLUE supports registered azurefactory/register.json only.
No workflow was dispatched and no deployment was performed.
Initialize locally: bash ./01b-BYORepo-init-template-files-once.sh
Then inspect the registered CLI:
  bash ./azurefactory.sh api instructions
  bash ./azurefactory.sh doctor
  bash ./azurefactory.sh factory create --help
  bash ./azurefactory.sh runtime deploy --help
Configuration/runtime operations require a separately installed, authenticated API.
Review the registered preview/receipt and approve separately; no API service is bundled here."""

# The pinned installer has no dry-run option. In a separate -B interpreter,
# intercept only its Merge.execute boundary, after upstream validates/collects
# the complete inventory and before any writes or register initialization.
# An audit guard also refuses Python filesystem mutations. Actual installation
# runs the unmodified upstream entry point, not this collector.
READ_ONLY_PLAN = r'''
import json
import os
from pathlib import Path
import sys

def read_only(event, args):
    if event == "open":
        mode, flags = args[1], args[2]
        if (isinstance(mode, str) and any(c in mode for c in "wax+")) or (
                isinstance(flags, int) and flags & (os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_TRUNC | os.O_APPEND)):
            raise ValueError("Read-only registered plan refused a file write.")
    if event in {"os.mkdir", "os.remove", "os.rmdir", "os.rename", "os.link",
                 "os.symlink", "os.chmod", "os.chown", "os.utime", "shutil.copyfile"}:
        raise ValueError("Read-only registered plan refused a filesystem mutation.")

sys.addaudithook(read_only)
source, root = Path(sys.argv[1]), Path(sys.argv[2])
sys.path.insert(0, str(source / "bootstrap" / "lib"))
import registered_setup

class PlanReady(BaseException):
    pass

class ReadOnlyMerge(registered_setup.Merge):
    def execute(self):
        if any(not isinstance(origin, Path) for origin in self.files.values()):
            raise ValueError("Registered installer inventory changed; review the BLUE collector.")
        print("BLUE_REGISTERED_PLAN=" + json.dumps(
            [[str(destination), str(origin)] for destination, origin in self.files.items()]))
        raise PlanReady()

registered_setup.Merge = ReadOnlyMerge
try:
    registered_setup.install(source, root, provider=sys.argv[3], refresh_only=sys.argv[4] == "true")
except PlanReady:
    pass
except (OSError, ValueError) as exc:
    print(str(exc), file=sys.stderr)
    sys.exit(2)
else:
    sys.exit("Registered installer did not reach its read-only planning boundary.")
'''


def local_environment():
    return {**os.environ, "GIT_TERMINAL_PROMPT": "0", "GCM_INTERACTIVE": "Never",
            "GIT_OPTIONAL_LOCKS": "0", "PYTHONDONTWRITEBYTECODE": "1"}


def git(root, *args, required=True):
    result = subprocess.run(
        ["git", "-C", str(root), *args], capture_output=True, check=False,
        env=local_environment(),
    )
    if result.returncode and required:
        raise ValueError(f"Git failed ({' '.join(args[:2])}); verify the consumer repository and selected gitlink.")
    return result.stdout if result.returncode == 0 else b""


def ordinary(path):
    for item in (path, *path.parents):
        try:
            info = item.lstat()
        except FileNotFoundError:
            continue
        if stat.S_ISLNK(info.st_mode) or getattr(info, "st_file_attributes", 0) & 0x400:
            raise ValueError(f"Symlinks and junctions are not supported: {item}")
        if not (stat.S_ISDIR(info.st_mode) or stat.S_ISREG(info.st_mode)):
            raise ValueError(f"Expected an ordinary file or directory: {item}")
        if stat.S_ISREG(info.st_mode) and info.st_nlink != 1:
            raise ValueError(f"Hard-linked files are not supported: {item}")
    return path


def validate_consumer(root):
    ordinary(root)
    if not ordinary(root / ".git").exists():
        raise ValueError("Select an existing consumer Git repository root.")
    top = Path(git(root, "rev-parse", "--show-toplevel").decode().strip())
    if top.resolve() != root.resolve():
        raise ValueError("Select the consumer Git repository root, not a nested directory.")
    if ordinary(root / "aifactory").exists():
        raise ValueError("Legacy aifactory exists. Use reviewed migration or a separate registered consumer; nothing is removed.")


def module_metadata(root):
    path = ordinary(root / ".gitmodules")
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
    validate_consumer(root)
    entry = git(root, "ls-files", "--stage", "--", SUBMODULE).decode().split()
    if entry and (len(entry) != 4 or entry[0] != "160000" or entry[1] != expected or entry[2] != "0"):
        raise ValueError("Repair will not replace existing tracked files or a different gitlink pin.")
    source = ordinary(root / SUBMODULE)
    if source.exists():
        if not source.is_dir():
            raise ValueError("Repair refuses a populated/non-directory submodule path.")
        if not entry and any(source.iterdir()):
            raise ValueError("Repair refuses a populated untracked submodule path; preserve/move it aside manually.")
        if ordinary(source / ".git").exists():
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
    validate_consumer(root)
    metadata = module_metadata(root)
    if metadata["path"] != SUBMODULE or not metadata["url"]:
        raise ValueError("Missing .gitmodules registration; use 01b --repair-submodule explicitly.")
    if metadata["branch"] not in ("", BRANCH):
        raise ValueError("Submodule branch metadata conflicts with the selected release.")
    entry = git(root, "ls-files", "--stage", "--", SUBMODULE).decode().split()
    if len(entry) != 4 or entry[0] != "160000" or entry[1] != expected or entry[2] != "0":
        raise ValueError(f"The consumer gitlink must select {expected}; use --repair-submodule only if it is missing.")
    source = ordinary(root / SUBMODULE)
    if ordinary(source / ".git").exists():
        if git(source, "status", "--porcelain", "--untracked-files=all"):
            raise ValueError("The source submodule is dirty/modified; preserve those edits before continuing.")
        if git(source, "rev-parse", "HEAD").decode().strip() != expected:
            raise ValueError("The initialized submodule differs from the selected pin; no checkout was performed.")
        return source
    if source.exists() and (not source.is_dir() or any(source.iterdir())):
        raise ValueError("Refusing populated source files without submodule metadata; preserve them manually.")
    if dry_run:
        print(f"Would initialize {SUBMODULE} at recorded gitlink {expected}; no files changed.")
        print("Registered helper/register validation is deferred until the selected source is available.")
        return None
    git(root, "submodule", "update", "--init", "--recursive", "--", SUBMODULE)
    if git(source, "rev-parse", "HEAD").decode().strip() != expected:
        raise ValueError("Submodule initialization did not produce the selected pin.")
    if git(source, "status", "--porcelain", "--untracked-files=all"):
        raise ValueError("Initialized source is dirty/modified; helper installation was not started.")
    return source


def normalized(data):
    return data.replace(b"\r\n", b"\n")


def scoped_workflow(root, source, provider):
    """The registered installer omits this separately published, manual-only GHA contract."""
    if provider == "ado":
        return {}
    origin = ordinary(source / SCOPED_GHA_TEMPLATE)
    if not origin.is_file():
        raise ValueError("Missing pinned scoped GitHub workflow template.")
    for directory in (root / ".github", root / SCOPED_GHA.parent):
        ordinary(directory)
        if directory.exists() and not directory.is_dir():
            raise ValueError(f"Cannot replace a file with a workflow directory: {directory}")
    destination = ordinary(root / SCOPED_GHA)
    if destination.exists() and not destination.is_file():
        raise ValueError(f"Cannot replace a directory with a workflow file: {destination}")
    return {destination: origin}


def build_plan(root, source, *, provider="both", refresh_only=False):
    """Read the actual pinned installer inventory without writing or reproducing its copy list."""
    root, source = Path(root).absolute(), Path(source).absolute()
    validate_consumer(root)
    ordinary(source)
    if provider not in {"both", "ado", "gha"}:
        raise ValueError("Select provider both, ado or gha.")
    if source == root or not ordinary(source / ".git").exists():
        raise ValueError("An existing reviewed Git source checkout, separate from the consumer, is required.")
    if git(source, "rev-parse", "HEAD").decode().strip() != PIN:
        raise ValueError("Source checkout differs from the selected pin; no checkout was performed.")
    if git(source, "status", "--porcelain", "--untracked-files=all"):
        raise ValueError("The source submodule is dirty/modified; preserve those edits before continuing.")
    if not ordinary(source / ENTRY_POINTS["registered_installer"]).is_file():
        raise ValueError("Missing immutable upstream registered installer.")
    result = subprocess.run(
        [sys.executable, "-B", "-c", READ_ONLY_PLAN, str(source), str(root),
         provider, str(refresh_only).lower()],
        cwd=root, env=local_environment(), capture_output=True, text=True, check=False,
    )
    if result.returncode:
        raise ValueError(result.stderr.strip() or "Registered installer preflight failed; no helper files changed.")
    prefix = "BLUE_REGISTERED_PLAN="
    inventories = [line[len(prefix):] for line in result.stdout.splitlines() if line.startswith(prefix)]
    if len(inventories) != 1:
        raise ValueError("Registered installer planning contract changed; no helper files changed.")
    files = {Path(destination): Path(origin) for destination, origin in json.loads(inventories[0])}
    files.update(scoped_workflow(root, source, provider))
    for destination, origin in files.items():
        destination.relative_to(root)
        origin.relative_to(source)
        if destination.exists() and normalized(destination.read_bytes()) != normalized(origin.read_bytes()):
            raise ValueError(f"Locally modified helper conflicts with the selected source; review and move it aside: {destination}")
    return files


def refresh(root, source, *, dry_run=False, provider="both", refresh_only=False):
    root, source = Path(root).absolute(), Path(source).absolute()
    files = build_plan(root, source, provider=provider, refresh_only=refresh_only)
    if dry_run:
        print(f"Registered plan: {len(files)} upstream helper/workflow files; provider={provider}; no files changed.")
        print("Existing register/configuration and provider helpers are preserved; no Azure/provider operation ran.")
        print("Register initialization: " + ("disabled (refresh only)." if refresh_only else "empty starter only if absent."))
        if provider in {"ado", "both"}:
            print(ADO_LIMITATION)
        return
    command = [sys.executable, "-B", str(source / ENTRY_POINTS["registered_installer"]),
               "--source", str(source), "--consumer-root", str(root), "--provider", provider]
    if refresh_only:
        command.append("--refresh-only")
    result = subprocess.run(command, cwd=root, env=local_environment(),
                            capture_output=True, text=True, check=False)
    if result.stdout:
        print(result.stdout, end="")
    if result.returncode:
        raise ValueError(result.stderr.strip() or "Upstream registered installation failed; no success is claimed.")
    for destination, origin in scoped_workflow(root, source, provider).items():
        payload = origin.read_bytes()
        if destination.exists():
            if normalized(destination.read_bytes()) != normalized(payload):
                raise ValueError(f"Scoped workflow changed during installation; preserved for review: {destination}")
        else:
            destination.parent.mkdir(parents=True, exist_ok=True)
            with destination.open("xb") as stream:
                stream.write(payload)
        print(f"Pinned manual-only scoped GitHub workflow ready (not dispatched): {destination}")
    if provider in {"ado", "both"}:
        print(ADO_LIMITATION)
    print(f"Registered consumer helpers ready at {PIN} ({BRANCH}); no Azure or provider operation ran.")


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    if argv and argv[0] == "deploy":
        if argv[1:] in (["--help"], ["-h"]):
            argparse.ArgumentParser(
                prog="04ab-setup-infra-aifactory.sh",
                description=DEPLOY_DIAGNOSTIC.removeprefix("ERROR: "),
                formatter_class=argparse.RawDescriptionHelpFormatter,
            ).print_help()
            return 0
        print(DEPLOY_DIAGNOSTIC, file=sys.stderr)
        return 2
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("operation", choices=("init", "refresh"))
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--provider", choices=("both", "ado", "gha"), default="both",
                        help="Registered wrappers and scoped GHA workflow; never remove another provider's files.")
    parser.add_argument("--dry-run", action="store_true", help="Read-only upstream inventory/register validation; never write.")
    parser.add_argument("--repair-submodule", action="store_true",
                        help="Init only: explicitly repair missing registration/gitlink; refuse populated untracked paths.")
    args = parser.parse_args(argv)
    try:
        root = args.root.absolute()
        validate_consumer(root)
        if args.repair_submodule:
            if args.operation != "init":
                raise ValueError("--repair-submodule applies only to init (01b).")
            repair_submodule(root, dry_run=args.dry_run)
            if args.dry_run:
                source = root / SUBMODULE
                if (source / ".git").exists():
                    refresh(root, source, dry_run=True, provider=args.provider)
                else:
                    print("Helper/register validation is deferred until the selected source is available.")
                return 0
        source = ensure_submodule(root, dry_run=args.dry_run)
        if source is not None:
            refresh(root, source, dry_run=args.dry_run, provider=args.provider,
                    refresh_only=args.operation == "refresh")
    except (OSError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
