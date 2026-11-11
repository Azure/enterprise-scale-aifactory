"""Shell entry points must survive Windows autocrlf checkout and another cwd."""

import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]


class ShellCheckoutTests(unittest.TestCase):
    def test_autocrlf_clone_preserves_executable_shell_contract(self):
        attributes = ROOT / ".gitattributes"
        self.assertTrue(attributes.is_file(), "Fresh Windows clones need LF shell attributes.")
        with tempfile.TemporaryDirectory(prefix=".bootstrap-test-shell-", dir=ROOT) as directory:
            root = Path(directory)
            source, clone = root / "source", root / "clone"
            source.mkdir()
            shutil.copy2(attributes, source / ".gitattributes")
            scripts = sorted(ROOT.glob("*.sh"))
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
