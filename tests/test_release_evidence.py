import importlib.util
import subprocess
import unittest
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
SHA = "a" * 40


class ReleaseEvidenceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        spec = importlib.util.spec_from_file_location(
            "release_evidence", ROOT / "bootstrap/release_evidence.py"
        )
        cls.module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cls.module)

    def run_record(self, **overrides):
        return {
            "id": 123,
            "head_sha": SHA,
            "head_branch": "release/v1.25",
            "event": "push",
            "status": "completed",
            "conclusion": "success",
            "path": ".github/workflows/bootstrap-consumer-tests.yml",
            "html_url": "https://github.com/owner/repo/actions/runs/123",
            **overrides,
        }

    def jobs(self):
        return {
            "jobs": [
                {"name": f"Bootstrap ({os})", "conclusion": "success"}
                for os in ("ubuntu-latest", "windows-latest")
            ]
        }

    def test_selects_success_for_exact_release_sha_and_both_platforms(self):
        with patch.object(
            self.module, "api",
            side_effect=[{"workflow_runs": [self.run_record()]}, self.jobs()],
        ):
            result = self.module.find_evidence("owner/repo", SHA)
        self.assertEqual(result["headSha"], SHA)
        self.assertEqual(result["runId"], 123)

    def test_rejects_other_sha_branch_pr_and_incomplete_runs(self):
        for override in (
            {"head_sha": "b" * 40},
            {"head_branch": "main"},
            {"event": "pull_request"},
            {"conclusion": "failure"},
            {"status": "in_progress"},
            {"path": ".github/workflows/unrelated.yml"},
        ):
            with self.subTest(override=override), patch.object(
                self.module, "api",
                return_value={"workflow_runs": [self.run_record(**override)]},
            ):
                with self.assertRaises(self.module.EvidenceError):
                    self.module.find_evidence("owner/repo", SHA)

    def test_requires_windows_and_linux_not_skipped(self):
        for jobs in (
            {"jobs": self.jobs()["jobs"][:1]},
            {"jobs": [{"name": "Bootstrap (windows-latest)", "conclusion": "skipped"}]},
        ):
            with patch.object(
                self.module, "api",
                side_effect=[{"workflow_runs": [self.run_record()]}, jobs],
            ):
                with self.assertRaises(self.module.EvidenceError):
                    self.module.find_evidence("owner/repo", SHA)

    def test_auth_failure_does_not_return_success(self):
        with patch.object(
            self.module.subprocess, "run",
            return_value=subprocess.CompletedProcess(["gh"], 1, "", "private-data"),
        ):
            with self.assertRaisesRegex(self.module.EvidenceError, "GitHub API"):
                self.module.api("repos/owner/repo/actions/runs")

    def test_rejects_invalid_repository_or_sha_before_api(self):
        with patch.object(self.module, "api") as api:
            for repo, sha in (("https://user:token@host/repo", SHA), ("owner/repo", "main")):
                with self.assertRaises(self.module.EvidenceError):
                    self.module.find_evidence(repo, sha)
            api.assert_not_called()


if __name__ == "__main__":
    unittest.main()
