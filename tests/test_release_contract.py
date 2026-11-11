"""Release documentation and credential-free CI contracts."""

import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PIN = "89eca66185366a702b026cec8c938570548c649c"
CAPTION = (
    "Figure: Each team in the AI Factory, have their own floor with 1-35 resources, "
    "optinally to get above architectures. Each team can own multiple floors. "
    "You may turn ON/OFF Azure resources to remove cost. Easy to turn on again."
)
IMAGE_ROOT = (
    "https://raw.githubusercontent.com/jostrm/azure-enterprise-scale-ml/"
    "main/documentation/v2/10-19/images/"
)


class ReleaseContractTests(unittest.TestCase):
    def test_setup_pages_link_to_full_release_guide(self):
        link = (
            "[Full setup & usage guide]"
            "(https://github.com/jostrm/azure-enterprise-scale-ml/blob/"
            "release/v1.25/documentation/v2/20-29/24-end-2-end-setup.md)"
        )
        for relative in ("README.md", "documentation/bootstrapping.md"):
            with self.subTest(page=relative):
                text = (ROOT / relative).read_text(encoding="utf-8")
                self.assertIn(link, text)
                self.assertLess(text.index(link), text.index("## "))

    def test_registered_only_onboarding_contract(self):
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        notes = (ROOT / "bootstrap/release-notes.txt").read_text(encoding="utf-8")
        docs = (ROOT / "documentation/bootstrapping.md").read_text(encoding="utf-8")
        self.assertIn("v1.25 and newer only", readme)
        self.assertIn("azurefactory/register.json", readme)
        self.assertIn("01-start-v125-and-above.sh", docs)
        self.assertIn("registered_setup.py", docs)
        self.assertIn("No legacy", notes)
        self.assertNotIn("supported legacy", docs)
        self.assertNotIn("supported layout is the upstream **legacy", docs)
        self.assertNotIn("bash 04ab-setup-infra-aifactory.sh --repo", docs)
        self.assertFalse((ROOT / "aifactory").exists())
        self.assertEqual(list((ROOT / ".github/workflows").glob("infra-*.yml")), [])

    def test_ci_long_paths_configured_before_recursive_checkout(self):
        text = (ROOT / ".github/workflows/bootstrap-consumer-tests.yml").read_text(encoding="utf-8")
        for value in ("GIT_CONFIG_COUNT: '1'", "GIT_CONFIG_KEY_0: core.longpaths",
                      "GIT_CONFIG_VALUE_0: 'true'"):
            self.assertIn(value, text)
            self.assertLess(text.index(value), text.index("uses: actions/checkout@"))

    def test_pinned_upstream_document_links_exist_in_selected_release(self):
        prefix = f"https://github.com/jostrm/azure-enterprise-scale-ml/blob/{PIN}/"
        for relative in ("README.md", "documentation/bootstrapping.md"):
            text = (ROOT / relative).read_text(encoding="utf-8")
            for href in re.findall(r"\]\(([^)]+)\)", text):
                if href.startswith(prefix):
                    target = href[len(prefix):].split("#", 1)[0]
                    self.assertTrue(
                        (ROOT / "azure-enterprise-scale-ml" / target).exists(),
                        f"{relative}: source path absent from selected release: {target}",
                    )

    def test_readme_is_short_consumer_specific_and_has_exact_cutoff(self):
        text = (ROOT / "README.md").read_text(encoding="utf-8")
        self.assertIn(
            "BLUE bootstraps your consumer repository; PURPLE supplies the versioned "
            "shared implementation through a Git submodule.",
            text[:1200],
        )
        self.assertLess(len(text), 6500)
        self.assertEqual(text.rstrip().split("\n\n")[-1], CAPTION)
        self.assertIn("ongoing costs", text)
        self.assertLess(text.index("Quickstart"), text.index(CAPTION))
        for image in (
            "14-eslz-full-1.png",
            "10-factory-onion-architecture-v2.gif",
            "10-two-architectures-v2-small.png",
            "concepts/mlops.gif",
            "concepts/dataops-rag.gif",
        ):
            self.assertIn(IMAGE_ROOT + image, text)
        self.assertNotRegex(text, r"!\[\s*\]\(")

    def test_local_documentation_links_resolve(self):
        for relative in ("README.md", "documentation/bootstrapping.md"):
            document = ROOT / relative
            text = document.read_text(encoding="utf-8")
            for href in re.findall(r"\]\(([^)]+)\)", text):
                if "://" in href or href.startswith(("#", "mailto:")):
                    continue
                target = href.split("#", 1)[0]
                self.assertTrue(
                    (document.parent / target).exists(),
                    f"{relative}: broken local link {href}",
                )

    def test_onboarding_covers_platform_boundary_and_pin(self):
        text = (ROOT / "documentation/bootstrapping.md").read_text(encoding="utf-8")
        for required in (
            PIN,
            "Include all branches",
            "is_template",
            "default branch",
            "gitlink",
            "dev/test/prod",
            "Azure DevOps",
            "submodules: recursive",
            "Compatibility matrix",
            "AZURE_CREDENTIALS",
            "OIDC",
            "release_125",
            "--latest=false",
            "headSha",
        ):
            self.assertIn(required, text)
        self.assertIn("not tested", text.lower())

    def test_ci_covers_release_and_both_shell_platforms(self):
        path = ROOT / ".github/workflows/bootstrap-consumer-tests.yml"
        self.assertTrue(path.exists())
        text = path.read_text(encoding="utf-8")
        for required in (
            "push:",
            "pull_request:",
            "release/v1.25",
            "workflow_dispatch:",
            "ubuntu-latest",
            "windows-latest",
            "shell: bash",
            "submodules: recursive",
            "persist-credentials: false",
            "contents: read",
            "github.sha",
            "test_release_contract.py",
            "test_*git.py",
        ):
            self.assertIn(required, text)
        self.assertNotIn("secrets.", text)
        self.assertNotIn("pull_request_target", text)

    def test_release_notes_use_selected_upstream_not_main(self):
        path = ROOT / "bootstrap/release-notes.txt"
        self.assertTrue(path.exists())
        text = path.read_text(encoding="utf-8")
        self.assertIn(PIN, text)
        self.assertIn("available through the submodule", text)
        self.assertIn("No Azure deployment", text)


if __name__ == "__main__":
    unittest.main()
