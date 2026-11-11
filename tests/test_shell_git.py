"""Shell entry points must survive Windows autocrlf checkout and another cwd."""

import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]


class ShellCheckoutTests(unittest.TestCase):
    script_names = (
        "01a-GH-mirror-repo-from-template-once.sh",
        "01b-BYORepo-init-template-files-once.sh",
        "02b-GH-create-or-update-github-variables.sh",
        "03b-GH-add-aifactory-pipelines-once.sh",
        "04ab-setup-infra-aifactory.sh",
    )

    def test_only_blue_wrappers_are_executed_not_generated_upstream_launchers(self):
        self.assertEqual(set(self.script_names), {
            "01a-GH-mirror-repo-from-template-once.sh",
            "01b-BYORepo-init-template-files-once.sh",
            "02b-GH-create-or-update-github-variables.sh",
            "03b-GH-add-aifactory-pipelines-once.sh",
            "04ab-setup-infra-aifactory.sh",
        })

    def test_job_scoped_longpaths_reaches_recursive_submodule_checkout(self):
        with tempfile.TemporaryDirectory(prefix=".bootstrap-test-longpath-", dir=ROOT) as directory:
            root = Path(directory)
            source, consumer, clone = root / "source", root / "consumer", root / "clone"
            environment = {
                **os.environ,
                "GIT_CONFIG_COUNT": "1",
                "GIT_CONFIG_KEY_0": "core.longpaths",
                "GIT_CONFIG_VALUE_0": "true",
            }

            def git(*args):
                return subprocess.run(
                    ["git", "-c", "protocol.file.allow=always", *args],
                    check=True, capture_output=True, text=True, env=environment,
                ).stdout.strip()

            for path in (source, consumer):
                git("init", str(path))
                git("-C", str(path), "config", "user.name", "Bootstrap test")
                git("-C", str(path), "config", "user.email", "test@example.invalid")
            relative = Path("nested-" + "a" * 70) / ("b" * 70) / ("c" * 70) / "notebook.ipynb"
            notebook = source / relative
            notebook.parent.mkdir(parents=True)
            notebook.write_text('{"cells":[]}', encoding="utf-8")
            git("-C", str(source), "add", ".")
            git("-C", str(source), "commit", "-m", "Long upstream path")
            git("-C", str(consumer), "submodule", "add", str(source), "upstream")
            git("-C", str(consumer), "commit", "-am", "Pinned submodule")
            git("clone", "--recurse-submodules", str(consumer), str(clone))
            self.assertEqual((clone / "upstream" / relative).read_text(), '{"cells":[]}')
            self.assertEqual(git("-C", str(clone / "upstream"), "config", "--get", "core.longpaths"), "true")

    def test_autocrlf_clone_preserves_executable_shell_contract(self):
        attributes = ROOT / ".gitattributes"
        self.assertTrue(attributes.is_file(), "Fresh Windows clones need LF shell attributes.")
        with tempfile.TemporaryDirectory(prefix=".bootstrap-test-shell-", dir=ROOT) as directory:
            root = Path(directory)
            source, clone = root / "source", root / "clone"
            source.mkdir()
            shutil.copy2(attributes, source / ".gitattributes")
            scripts = [ROOT / name for name in self.script_names]
            for path in scripts:
                shutil.copy2(path, source / path.name)
            (source / "bootstrap").mkdir()
            for name in ("consumer.py", "github_bootstrap.py", "github-settings.json"):
                shutil.copy2(ROOT / "bootstrap" / name, source / "bootstrap" / name)

            def git(*args):
                subprocess.run(
                    ["git", *args], check=True, stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE, cwd=root,
                )

            git("init", str(source))
            git("-C", str(source), "config", "user.name", "Bootstrap test")
            git("-C", str(source), "config", "user.email", "test@example.invalid")
            git("-C", str(source), "add", ".")
            git("-C", str(source), "commit", "-m", "shell fixture")
            git("-c", "core.autocrlf=true", "clone", str(source), str(clone))
            bash = shutil.which("bash")
            if os.name == "nt":
                git_bash = Path(os.environ.get("ProgramFiles", r"C:\Program Files")) / "Git/bin/bash.exe"
                if git_bash.is_file():
                    bash = str(git_bash)
            self.assertIsNotNone(bash, "Bash is a required test prerequisite.")
            for script in scripts:
                checked_out = clone / script.name
                self.assertNotIn(b"\r\n", checked_out.read_bytes(), script.name)
                result = subprocess.run(
                    [bash, str(checked_out), "--help"], cwd=root,
                    text=True, capture_output=True, timeout=30, check=False,
                )
                self.assertEqual(result.returncode, 0, f"{script.name}: {result.stderr}")
                self.assertIn("usage:", result.stdout)


if __name__ == "__main__":
    unittest.main()
