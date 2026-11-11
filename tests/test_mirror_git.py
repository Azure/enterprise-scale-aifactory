from pathlib import Path
import subprocess
import tempfile
import unittest

from bootstrap import github_bootstrap as gb


ROOT = Path(__file__).resolve().parents[1]


class MirrorGitTests(unittest.TestCase):
    def setUp(self):
        self.workspace = tempfile.TemporaryDirectory(dir=ROOT, prefix=".bootstrap-test-")
        self.addCleanup(self.workspace.cleanup)
        self.root = Path(self.workspace.name)
        self.source = self.root / "source.git"
        self.destination = self.root / "destination.git"
        self.work = self.root / "work"
        self.git("init", "--bare", str(self.source))
        self.git("init", "--bare", str(self.destination))
        self.git("init", str(self.work))
        self.git("-C", str(self.work), "config", "user.email", "test@example.invalid")
        self.git("-C", str(self.work), "config", "user.name", "Test")
        (self.work / "file.txt").write_text("history", encoding="utf-8")
        self.git("-C", str(self.work), "add", "file.txt")
        self.git("-C", str(self.work), "commit", "-m", "history")
        self.git("-C", str(self.work), "tag", "v1")
        (self.work / "file.txt").write_text("second commit", encoding="utf-8")
        self.git("-C", str(self.work), "commit", "-am", "second")
        self.git("-C", str(self.work), "branch", "release/v1.25")
        self.git("-C", str(self.work), "update-ref", "refs/notes/audit", "HEAD")
        self.git("-C", str(self.work), "push", "--mirror", str(self.source))

    def git(self, *args):
        return subprocess.check_output(["git", *args], stderr=subprocess.STDOUT, text=True).strip()

    def refs(self, repo):
        return self.git("--git-dir", str(repo), "show-ref")

    def test_actual_mirror_copies_all_refs_and_history_and_cleans(self):
        source_before = self.refs(self.source)
        gb.mirror_git(gb.Runner(), str(self.source), str(self.destination),
                      "release/v1.25", self.root)
        self.assertEqual(source_before, self.refs(self.destination))
        self.assertEqual(source_before, self.refs(self.source))
        self.assertEqual("2", self.git("--git-dir", str(self.destination), "rev-list", "--count", "refs/heads/release/v1.25"))
        self.assertEqual("history", self.git("--git-dir", str(self.destination), "show", "v1:file.txt"))
        self.assertFalse(list(self.root.glob(".bootstrap-mirror-*")))

    def test_nonempty_destination_refused_unchanged(self):
        self.git("-C", str(self.work), "push", str(self.destination), "HEAD:refs/heads/keep")
        before = self.refs(self.destination)
        with self.assertRaises(gb.BootstrapError):
            gb.mirror_git(gb.Runner(), str(self.source), str(self.destination),
                          "release/v1.25", self.root)
        self.assertEqual(before, self.refs(self.destination))
        self.assertFalse(list(self.root.glob(".bootstrap-mirror-*")))

    def test_failed_clone_leaves_user_checkout_and_no_temp(self):
        with self.assertRaises(gb.BootstrapError):
            gb.mirror_git(gb.Runner(), str(self.root / "absent.git"), str(self.destination),
                          "release/v1.25", self.root)
        self.assertTrue((self.work / "file.txt").exists())
        self.assertFalse(list(self.root.glob(".bootstrap-mirror-*")))

    def test_missing_branch_refused_before_push(self):
        with self.assertRaises(gb.BootstrapError):
            gb.mirror_git(gb.Runner(), str(self.source), str(self.destination), "release/v1.26", self.root)
        self.assertEqual("", self.git("ls-remote", str(self.destination)))

    def test_older_release_selection_refused_but_historical_refs_are_preserved(self):
        self.git("-C", str(self.work), "branch", "release/v1.24", "v1")
        self.git("-C", str(self.work), "push", "--mirror", str(self.source))
        with self.assertRaisesRegex(gb.BootstrapError, "v1.25"):
            gb.mirror_git(gb.Runner(), str(self.source), str(self.destination), "release/v1.24", self.root)
        self.assertEqual("", self.git("ls-remote", str(self.destination)))
        gb.mirror_git(gb.Runner(), str(self.source), str(self.destination), "release/v1.25", self.root)
        self.assertEqual(self.refs(self.source), self.refs(self.destination))

    def test_ignore_rules_protect_runtime_state_without_hiding_register_or_template(self):
        protected = (".env", ".env.local", "azurefactory/.azurefactory/operations.sqlite",
                     ".azurefactory-tools/azurefactory/cli.py", "receipts/approval.json",
                     "factory.receipt.json", "factory.review.json", "factory.private.json",
                     "factory-receipt.json", "receipt.json", ".aifactory-backups/config.json")
        public = (".env.template", "azurefactory/register.json", "azurefactory/factory/settings.json")
        for source in (".gitignore", ".gitignore.template"):
            (self.work / ".gitignore").write_bytes((ROOT / source).read_bytes())
            for path in protected + public:
                result = subprocess.run(["git", "-C", str(self.work), "check-ignore", "--no-index", "-q", "--", path],
                                        capture_output=True, check=False)
                with self.subTest(source=source, path=path):
                    self.assertEqual(result.returncode, 0 if path in protected else 1)

    def test_destination_populated_during_clone_refuses_and_cleans(self):
        test = self

        class PopulateDuringClone(gb.Runner):
            def run(self, args, **kwargs):
                output = super().run(args, **kwargs)
                if "clone" in args:
                    test.git("-C", str(test.work), "push", str(test.destination), "HEAD:refs/heads/keep")
                return output

        with self.assertRaises(gb.BootstrapError):
            gb.mirror_git(PopulateDuringClone(), str(self.source), str(self.destination),
                          "release/v1.25", self.root)
        self.assertIn("refs/heads/keep", self.refs(self.destination))
        self.assertNotIn("refs/heads/release/v1.25", self.refs(self.destination))
        self.assertFalse(list(self.root.glob(".bootstrap-mirror-*")))

    def test_push_failure_is_propagated_and_owned_clone_cleaned(self):
        class RejectPush(gb.Runner):
            def run(self, args, **kwargs):
                if "push" in args:
                    raise gb.BootstrapError("Push rejected")
                return super().run(args, **kwargs)

        with self.assertRaisesRegex(gb.BootstrapError, "Push rejected"):
            gb.mirror_git(RejectPush(), str(self.source), str(self.destination), "release/v1.25", self.root)
        self.assertFalse(list(self.root.glob(".bootstrap-mirror-*")))
        self.assertTrue((self.work / "file.txt").exists())

    def test_native_template_gitlink_repair_pins_without_deleting_consumer_files(self):
        generated = self.root / "generated-consumer"
        self.git("init", str(generated))
        self.git("-C", str(generated), "config", "user.email", "test@example.invalid")
        self.git("-C", str(generated), "config", "user.name", "Test")
        keep = generated / "consumer-owned.txt"
        keep.write_text("preserve generated repository", encoding="utf-8")
        self.git("-C", str(generated), "add", "consumer-owned.txt")
        self.git("-C", str(generated), "commit", "-m", "generated snapshot")
        module_name = "azure-enterprise-scale-ml"
        module = generated / module_name
        self.assertFalse((generated / ".gitmodules").exists())
        self.assertEqual("", self.git("-C", str(generated), "ls-files", "--stage", "--", module_name))
        pin = self.git("--git-dir", str(self.source), "rev-parse", "v1^{commit}")
        source_tip = self.git("--git-dir", str(self.source), "rev-parse", "refs/heads/release/v1.25")
        self.assertNotEqual(pin, source_tip)

        for key, value in (("path", module_name), ("url", str(self.source)), ("branch", "release/v1.25")):
            self.git("-C", str(generated), "config", "--file", ".gitmodules",
                     f"submodule.{module_name}.{key}", value)
        self.git("-C", str(generated), "add", ".gitmodules")
        self.git("-C", str(generated), "update-index", "--add", "--cacheinfo",
                 f"160000,{pin},{module_name}")
        self.git("-C", str(generated), "-c", "protocol.file.allow=always",
                 "submodule", "update", "--init", "--checkout", "--", module_name)

        self.assertEqual(pin, self.git("-C", str(module), "rev-parse", "HEAD"))
        self.assertEqual(f"160000 {pin} 0\t{module_name}",
                         self.git("-C", str(generated), "ls-files", "--stage", "--", module_name))
        self.assertEqual("preserve generated repository", keep.read_text(encoding="utf-8"))
        sentinel = module / "local-note.txt"
        sentinel.write_text("do not delete", encoding="utf-8")
        self.git("-C", str(generated), "-c", "protocol.file.allow=always",
                 "submodule", "update", "--init", "--checkout", "--", module_name)
        self.assertEqual(pin, self.git("-C", str(module), "rev-parse", "HEAD"))
        self.assertEqual("do not delete", sentinel.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
