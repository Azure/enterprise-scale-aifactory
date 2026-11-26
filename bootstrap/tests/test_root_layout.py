"""v1.26 slim root: four folders, one Markdown page, one entry script, and the PURPLE v1.26 pin."""

import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import unittest


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from bootstrap import consumer, release_evidence  # noqa: E402

FOLDERS = {".github", "azure-enterprise-scale-ml", "azurefactory", "bootstrap", "documentation"}
FILES = {".env.template", ".gitattributes", ".gitignore", ".gitmodules", "LICENSE", "README.md", "aifactory.sh"}
COMPLIANCE = ("CODE_OF_CONDUCT.md", "CONTRIBUTING.md", "SECURITY.md", "SUPPORT.md")
COMMANDS = {
    "mirror": "github_bootstrap.py mirror",
    "init": "consumer.py",
    "sync": "github_bootstrap.py sync",
    "refresh": "consumer.py",
    "deploy": "aifactory.sh deploy",
}
RETIRED = ("01a-GH-mirror-repo-from-template-once.sh", "01b-BYORepo-init-template-files-once.sh",
           "02b-GH-create-or-update-github-variables.sh", "03b-GH-add-aifactory-pipelines-once.sh",
           "04ab-setup-infra-aifactory.sh")
PURPLE_BRANCH = "release/v1.26"


def git(*args):
    return subprocess.run(["git", "-C", str(ROOT), *args], check=True, capture_output=True, text=True).stdout


def bash():
    if os.name == "nt":
        git_bash = Path(os.environ.get("ProgramFiles", r"C:\Program Files")) / "Git/bin/bash.exe"
        if git_bash.is_file():
            return str(git_bash)
    found = shutil.which("bash")
    assert found, "Bash is a required test prerequisite."
    return found


def run(*args):
    environment = {**os.environ, "AIFACTORY_PYTHON": sys.executable}
    return subprocess.run([bash(), str(ROOT / "aifactory.sh"), *args], cwd=ROOT, env=environment,
                          capture_output=True, text=True, timeout=60, check=False)


class RootLayoutTests(unittest.TestCase):
    def test_root_holds_only_the_slim_v126_entries(self):
        tracked = {line.split("/", 1)[0] for line in git("ls-files").splitlines()}
        self.assertEqual(tracked, FOLDERS | FILES)
        self.assertEqual({name for name in tracked if name.endswith(".md")}, {"README.md"})
        self.assertEqual(len(FOLDERS - {".github"}), 4)

    def test_compliance_pages_live_in_github_folder(self):
        for name in COMPLIANCE:
            with self.subTest(page=name):
                self.assertTrue((ROOT / ".github" / name).is_file())
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        for name in COMPLIANCE:
            self.assertIn(f"(.github/{name})", readme)

    def test_numbered_wrappers_are_retired_everywhere(self):
        for name in RETIRED:
            with self.subTest(script=name):
                result = subprocess.run(["git", "-C", str(ROOT), "grep", "-l", "-F", name, "--", ".",
                                         ":!bootstrap/tests"], capture_output=True, text=True, check=False)
                self.assertEqual((result.returncode, result.stdout), (1, ""), result.stderr)


class EntryScriptTests(unittest.TestCase):
    def test_each_command_reaches_its_bootstrap_entry_point(self):
        for command, usage in COMMANDS.items():
            with self.subTest(command=command):
                result = run(command, "--help")
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertIn("usage:", result.stdout)
                self.assertIn(usage, result.stdout)

    def test_init_and_refresh_select_their_consumer_operation(self):
        environment = {**os.environ, "AIFACTORY_PYTHON": sys.executable}
        for command in ("init", "refresh"):
            with self.subTest(command=command):
                result = subprocess.run([bash(), "-x", str(ROOT / "aifactory.sh"), command, "--help"],
                                        cwd=ROOT, env=environment, capture_output=True, text=True,
                                        timeout=60, check=False)
                self.assertRegex(result.stderr, rf"consumer\.py {command} --help")

    def test_missing_or_unknown_command_prints_usage_and_fails(self):
        for args in ((), ("deploy-all",)):
            with self.subTest(args=args):
                result = run(*args)
                self.assertEqual(result.returncode, 2)
                for command in COMMANDS:
                    self.assertIn(command, result.stderr)

    def test_help_lists_every_command(self):
        result = run("--help")
        self.assertEqual(result.returncode, 0, result.stderr)
        for command in COMMANDS:
            self.assertIn(command, result.stdout)

    def test_entry_script_is_lf_and_executable_in_git(self):
        self.assertNotIn(b"\r\n", (ROOT / "aifactory.sh").read_bytes())
        self.assertTrue(git("ls-files", "-s", "aifactory.sh").startswith("100755"))


class PurplePinTests(unittest.TestCase):
    def test_every_pin_names_the_submodule_commit_on_purple_v126(self):
        gitlink = git("ls-files", "--stage", "--", "azure-enterprise-scale-ml").split()[1]
        settings = json.loads((ROOT / "bootstrap/github-settings.json").read_text(encoding="utf-8"))
        self.assertEqual(consumer.PIN, gitlink)
        self.assertEqual(settings["upstream_commit"], gitlink)
        self.assertEqual(consumer.BRANCH, PURPLE_BRANCH)
        self.assertEqual(release_evidence.BRANCH, PURPLE_BRANCH)
        self.assertIn(f"branch = {PURPLE_BRANCH}", (ROOT / ".gitmodules").read_text(encoding="utf-8"))
        self.assertIn(gitlink, (ROOT / "bootstrap/release-notes.txt").read_text(encoding="utf-8"))

    def test_env_template_and_ci_follow_v126(self):
        env = (ROOT / ".env.template").read_text(encoding="utf-8")
        self.assertRegex(env, rf'(?m)^GITHUB_SOURCE_BRANCH="{re.escape(PURPLE_BRANCH)}"$')
        workflow = (ROOT / ".github/workflows/bootstrap-consumer-tests.yml").read_text(encoding="utf-8")
        self.assertEqual(workflow.count(PURPLE_BRANCH), 2)
        self.assertIn("-s bootstrap/tests", workflow)


if __name__ == "__main__":
    unittest.main()
