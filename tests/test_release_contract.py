"""Release documentation and credential-free CI contracts."""

import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PIN = "89eca66185366a702b026cec8c938570548c649c"
IMAGE_ROOT = (
    "https://raw.githubusercontent.com/jostrm/azure-enterprise-scale-ml/"
    "main/documentation/v2/10-19/images/"
)


class ReleaseContractTests(unittest.TestCase):
    def test_setup_pages_link_to_full_variable_documentation(self):
        link = (
            "[Full variable documentation]"
            "(https://jostrm.github.io/azure-enterprise-scale-ml/)"
        )
        for relative in ("README.md", "documentation/bootstrapping.md"):
            with self.subTest(page=relative):
                text = (ROOT / relative).read_text(encoding="utf-8")
                self.assertIn(link, text, f"{relative}: missing variable documentation link")
                self.assertLess(text.index(link), text.index("## "))

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
            for markdown, html in re.findall(r'\]\(([^)]+)\)|href="([^"]+)"', text):
                href = markdown or html
                if href.startswith(prefix):
                    target = href[len(prefix):].split("#", 1)[0]
                    self.assertTrue(
                        (ROOT / "azure-enterprise-scale-ml" / target).exists(),
                        f"{relative}: source path absent from selected release: {target}",
                    )

    def test_readme_opening_matches_upstream_artwork_before_consumer_welcome(self):
        text = (ROOT / "README.md").read_text(encoding="utf-8")
        self.assertEqual(text.count("\n# Welcome to BLUE\n"), 1)
        opening, consumer = text.split("\n# Welcome to BLUE\n")
        self.assertIn("BLUE consumer", opening.splitlines()[0])
        self.assertIn("PURPLE", opening)
        self.assertIn("Git submodule", opening)
        self.assertLess(len(opening), 8500)
        self.assertLess(len(consumer), 6500)
        self.assertIn(
            "BLUE bootstraps your consumer repository; PURPLE supplies the versioned "
            "shared implementation through a Git submodule.",
            consumer[:1200],
        )
        self.assertIn("ongoing costs", consumer)
        self.assertIn("## Quickstart - v1.25", consumer)
        self.assertIn("compatibility matrix", opening)
        self.assertNotIn("## Quickstart", opening)
        images = re.findall(r'!\[[^\]]*\]\(([^)]+)\)|<img\s+[^>]*src="([^"]+)"', opening)
        sources = [markdown or html for markdown, html in images]
        self.assertEqual(sources, [
            "https://aka.ms/deploytoazurebutton",
            IMAGE_ROOT + "header.png",
            IMAGE_ROOT + "14-eslz-full-1.png",
            IMAGE_ROOT.replace("10-19/images/", "20-29/images/")
            + "esaf-architecture-external-hub.png",
            IMAGE_ROOT + "10-factory-onion-architecture-v2.gif",
            IMAGE_ROOT + "10-two-architectures-v2-small.png",
            IMAGE_ROOT + "concepts/mlops.gif",
            IMAGE_ROOT + "concepts/dataops-rag.gif",
        ])
        for source in sources:
            self.assertEqual(text.count(source), 1)
        for pitch in ("WAF-aligned", "Dev, Stage and Prod", "54", "147",
                      "One governed lifecycle", "Private by design",
                      "Operating models included", "Subscription vending"):
            self.assertIn(pitch, opening)
        self.assertIn('<td width="50%" rowspan="2" valign="top">', opening)
        self.assertIn("No Azure deployment is performed by repository setup.", consumer)
        self.assertNotRegex(text, r"!\[\s*\]\(")

    def test_local_documentation_links_resolve(self):
        for relative in ("README.md", "documentation/bootstrapping.md"):
            document = ROOT / relative
            text = document.read_text(encoding="utf-8")
            for markdown, html in re.findall(r'\]\(([^)]+)\)|href="([^"]+)"', text):
                href = markdown or html
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
