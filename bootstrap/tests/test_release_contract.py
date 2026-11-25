"""Release documentation and credential-free CI contracts."""

import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
PIN = "a8b68eab54d00d7276ff4d8b659f940af8c37f94"
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
            "release/v1.26/documentation/v2/20-29/24-end-2-end-setup.md)"
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
        self.assertNotIn("bash aifactory.sh deploy --repo", docs)
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

    def test_readme_uses_public_repository_terminology(self):
        text = (ROOT / "README.md").read_text(encoding="utf-8")
        self.assertNotRegex(text, r"(?i)\b(?:blue|purple)\b")
        self.assertIn("This repo", text)
        self.assertIn("common functionality", text)

    def test_readme_opening_matches_upstream_artwork_before_consumer_welcome(self):
        text = (ROOT / "README.md").read_text(encoding="utf-8")
        self.assertEqual(text.count("\n# Welcome to this repo\n"), 1)
        opening, consumer = text.split("\n# Welcome to this repo\n")
        self.assertIn("consumer repository", opening.splitlines()[0])
        self.assertIn("common functionality", opening)
        self.assertIn("Git submodule", opening)
        self.assertLess(len(opening), 8500)
        self.assertLess(len(consumer), 6500)
        self.assertIn(
            "This repo bootstraps your consumer repository; versioned common "
            "functionality is supplied through a Git submodule.",
            consumer[:1200],
        )
        self.assertIn("ongoing costs", consumer)
        self.assertIn("## Quickstart - v1.26", consumer)
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
            "release_126",
            "--latest=false",
            "headSha",
        ):
            self.assertIn(required, text)
        self.assertIn("not tested", text.lower())

    def test_template_guide_covers_button_steps_and_post_creation_setup(self):
        text = (ROOT / "documentation/bootstrapping.md").read_text(encoding="utf-8")
        section = text.split("## B. GitHub Use this template\n", 1)[1].split(
            "## C. Empty Azure DevOps or bring your own repository\n", 1
        )[0]
        for required in (
            'How to use the "Use this template" button',
            "Create a new repository",
            "Owner",
            "Include all branches",
            "Create repository from template",
            "is_template=true",
            "2026-11-25",
            "Default-only",
            "current `main`",
            "not this v1.26 `aifactory.sh` layout",
            "--include-all-branches",
            "--default-branch release/v1.26",
            "160000",
            PIN,
            "aifactory.sh init --repair-submodule --dry-run",
            "aifactory.sh init --provider gha --dry-run",
            ".github/workflows/factory-lifecycle.yml",
            "aifactory.sh sync --dry-run",
            "GITHUB_DESTINATION_REPO",
            "workflow_dispatch",
            "not tested",
        ):
            with self.subTest(required=required):
                self.assertIn(required, section)
        self.assertNotIn("default remains older", section)
        self.assertNotIn("Default-only generation does not give", section)
        self.assertNotIn("setting was `false`", section)
        for retired in ("01a-", "01b-", "02b-", "03b-"):
            with self.subTest(retired=retired):
                self.assertNotIn(retired, section)
        self.assertNotIn("unchanged `main`", text)
        self.assertNotIn("release/v1.26` and `release/v1.26", text)

    def test_template_guide_compares_native_generation_with_actual_mirror_script(self):
        text = (ROOT / "documentation/bootstrapping.md").read_text(encoding="utf-8")
        comparison = text.split("### Template versus programmatic mirror: pros and cons\n", 1)[1]
        for required in (
            "aifactory.sh mirror",
            "single commit",
            "unrelated histories",
            "tags",
            "existing-empty",
            "--dry-run",
            "OIDC",
            "Git LFS",
            "not automatically",
            "Never run the mirror command against a template-created",
            "bootstrap/github_bootstrap.py",
            "bootstrap/consumer.py",
            "bootstrap/tests/test_mirror_git.py",
            "bootstrap/tests/test_consumer_git.py",
            "https://docs.github.com/en/repositories/creating-and-managing-repositories/duplicating-a-repository",
            "https://cli.github.com/manual/gh_repo_create",
        ):
            with self.subTest(required=required):
                self.assertIn(required, comparison)
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        self.assertIn(
            "[Button instructions and template-vs-mirror comparison]"
            "(documentation/bootstrapping.md#b-github-use-this-template)",
            readme,
        )

    def test_ci_covers_release_and_both_shell_platforms(self):
        path = ROOT / ".github/workflows/bootstrap-consumer-tests.yml"
        self.assertTrue(path.exists())
        text = path.read_text(encoding="utf-8")
        for required in (
            "push:",
            "pull_request:",
            "release/v1.26",
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
