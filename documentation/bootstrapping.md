# BLUE v1.25 consumer onboarding

BLUE owns repository bootstrap, consumer configuration and orchestration entry points.
PURPLE owns shared IaC, reusable pipelines and accelerator implementations.
Repository setup does not deploy Azure, create identities or credentials, register
providers, change Azure permissions, or launch an editor.

## Release baseline and prerequisites

This release selects PURPLE `release/v1.25` at
`89eca66185366a702b026cec8c938570548c649c`. Every source reference below means this
commit, not PURPLE `main` or a later branch tip.

Use Git, Bash and Python 3.10+; on Windows use Git for Windows **Git Bash**, with a
real Python interpreter on PATH, not a Windows Store alias. GitHub operations also
require GitHub CLI, authenticated repository/environment administration permissions,
workflow-write permissions where required, and organization SAML SSO authorization.
Organization-repository creation uses a conservative owner-permission preflight.
SSH additionally requires an authorized GitHub SSH key; HTTPS uses your credential
manager. Never embed credentials in remote URLs.

`.gitmodules` declares the submodule URL and `branch = release/v1.25`. That branch
metadata selects the branch for **explicit updates**. Ordinary recursive clones and
`git submodule update --init --recursive` reproduce the **committed gitlink**, even
when the upstream branch later advances. Bootstrap never uses `--remote` or
blanket submodule checkout commands.

## A. GitHub mirror

Clone BLUE's release branch locally:

```bash
git clone --branch release/v1.25 --recurse-submodules \
  https://github.com/Azure/enterprise-scale-aifactory.git blue-v125
cd blue-v125
cp .env.template .env
```

Edit your local `.env`: fill the repository policy and only the selected environment
values. Then preview and apply:

```bash
bash 01a-GH-mirror-repo-from-template-once.sh --dry-run
bash 01a-GH-mirror-repo-from-template-once.sh
```

Repository settings are `GITHUB_SOURCE_REPO`, `GITHUB_SOURCE_BRANCH`,
`GITHUB_DESTINATION_REPO`, `GITHUB_VISIBILITY`, `GITHUB_DESTINATION_STATE`,
`GITHUB_DEFAULT_BRANCH`, `GITHUB_TRANSPORT`, `GITHUB_ENVIRONMENTS` and
`GITHUB_AUTH_MODE`. The default `.env` is resolved beside the scripts, even when
invoked from another directory; an explicit `--env-file` is caller-relative.

The template explains each setting. CLI flags can explicitly override repository
policy, for example:

```bash
bash 01a-GH-mirror-repo-from-template-once.sh \
  --source Azure/enterprise-scale-aifactory --source-branch release/v1.25 \
  --destination YOUR-OWNER/YOUR-REPO --visibility private \
  --destination-state create --default-branch release/v1.25 \
  --transport https --environments dev --auth-mode oidc --env-file .env --dry-run
```

Use `create` for a new repository, or explicitly select `existing-empty` for an
already-created empty repository. A populated destination, source=destination,
unconfirmed permissions, API failure or ambiguous absence stops the operation.
An HTTP 404 is not treated as proof that a repository can safely be overwritten.
Dry-run performs read-only preflight; it does not prove that future creation will
be permitted.

This is a **full mirror**, not a release-only copy: `git clone --mirror` followed
by `git push --mirror --atomic` copies advertised Git refs and their history.
Both API permissions and destination emptiness are checked before the push.
Server-owned refs or organization policies can reject the mirror; there is no
filtered-ref, force-push or history-replacement fallback. Do not initialize a
destination README or license first, or allow concurrent writers during bootstrap.

A mirror does **not** copy repository settings, environment protection rules,
GitHub variables or secrets. After the Git push, the script selects the requested
release as the **destination** default branch and synchronizes the selected
environments. Configure Actions policy, reviewers, branch rules and federation
separately. BLUE's own default branch is never changed.

The script uses and cleans up only its own temporary bare clone; it does not
delete or replace a local consumer checkout. Clone your new repository yourself:

```bash
git clone --branch release/v1.25 --recurse-submodules \
  https://github.com/YOUR-OWNER/YOUR-REPO.git my-aifactory
cd my-aifactory
bash 01b-BYORepo-init-template-files-once.sh
```

For later configuration changes, use **only** the synchronization entry point:

```bash
bash 02b-GH-create-or-update-github-variables.sh --dry-run
bash 02b-GH-create-or-update-github-variables.sh
```

It does not clone, push, create a repository or change its default branch.
If an operation fails after a write, the error lists completed actions, returns
nonzero and does not attempt automatic rollback. Inspect GitHub before retrying;
never rerun mirror creation against the now-populated repository.

## B. GitHub Use this template

**Administrative prerequisite:** BLUE's public `is_template` setting was `false`
when this release was prepared. An administrator must enable **Template repository**
in repository Settings, or explicitly run:

```bash
gh repo edit Azure/enterprise-scale-aifactory --template
```

A code commit cannot enable that setting. An authorization failure must be resolved
through normal permissions/SSO; do not bypass it. This does not change BLUE's
default branch.

GitHub generation offers the **default branch or all branches**, not the arbitrary
branch currently being viewed. While BLUE's default branch remains `main`, choose
**Include all branches**. Default-branch-only generation would copy the older
BLUE `main`, not v1.25. Equivalent CLI, after the template setting is enabled:

```bash
gh repo create YOUR-OWNER/YOUR-REPO \
  --template Azure/enterprise-scale-aifactory --include-all-branches --private
git clone --branch release/v1.25 \
  https://github.com/YOUR-OWNER/YOUR-REPO.git my-aifactory
cd my-aifactory
```

Generated branches have new, unrelated histories. Do not merge the generated
`main` and `release/v1.25` merely to make v1.25 discoverable. With administrator
permission on **your generated consumer**, select the release as its default:

```bash
gh repo edit YOUR-OWNER/YOUR-REPO --default-branch release/v1.25
git branch --show-current
git ls-tree HEAD azure-enterprise-scale-ml
git config --file .gitmodules --get submodule.azure-enterprise-scale-ml.branch
git config --file .gitmodules --get submodule.azure-enterprise-scale-ml.url
git submodule update --init --recursive
git -C azure-enterprise-scale-ml rev-parse HEAD
bash 01b-BYORepo-init-template-files-once.sh
```

Expect a `160000` gitlink with SHA
`89eca66185366a702b026cec8c938570548c649c`, branch `release/v1.25`, and URL
`https://github.com/jostrm/azure-enterprise-scale-ml`. The initialized submodule
must report the same SHA.

**Platform boundary:** native GitHub template generation was **not tested** by
creating a disposable remote repository. Local Git tests prove cloning and
initialization, not GitHub's generation service. Inspect the generated metadata
and gitlink rather than assuming either survived. If they are absent, use this
explicit BLUE repair; it refuses a populated untracked source path and stages
only the reviewed gitlink, without committing or pushing:

```bash
bash 01b-BYORepo-init-template-files-once.sh --repair-submodule --dry-run
bash 01b-BYORepo-init-template-files-once.sh --repair-submodule
git diff --cached --submodule=log
git add .gitmodules azure-enterprise-scale-ml
git commit -m "Restore pinned v1.25 shared implementation"
git push origin release/v1.25
```

For a manual Git-only repair instead, use the following only after confirming the
path is absent or empty; if it contains
files or local work, stop and inspect rather than deleting it:

```bash
PURPLE_SHA=89eca66185366a702b026cec8c938570548c649c
git config --file .gitmodules submodule.azure-enterprise-scale-ml.path azure-enterprise-scale-ml
git config --file .gitmodules submodule.azure-enterprise-scale-ml.url https://github.com/jostrm/azure-enterprise-scale-ml
git config --file .gitmodules submodule.azure-enterprise-scale-ml.branch release/v1.25
git update-index --add --cacheinfo "160000,$PURPLE_SHA,azure-enterprise-scale-ml"
git submodule sync -- azure-enterprise-scale-ml
git submodule update --init --recursive
git add .gitmodules azure-enterprise-scale-ml
git commit -m "Restore pinned v1.25 shared implementation"
git push origin release/v1.25
```

Copy/edit `.env.template` and run the configuration-only script from route A.
Templates do not carry secrets, environment protection or repository settings.
`workflow_dispatch` discovery requires the workflow on the consumer default
branch; `--ref` alone does not make a release-only workflow discoverable while
an older `main` remains default.

References: [GitHub template generation](https://docs.github.com/en/repositories/creating-and-managing-repositories/creating-a-repository-from-a-template)
and [workflow events](https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows#workflow_dispatch).

## C. Empty Azure DevOps or bring your own repository

In Azure DevOps, create a project if needed, then **Repos > Files > repository
selector > New repository > Git**. Leave initialization with a README unchecked:
the destination must be empty. Use your organization's normal authentication
(Git Credential Manager or approved SSH), not a PAT inside the URL.

The repository administrator must grant Create repository if you create it,
Read/Contribute/Create branch for Git, and the appropriate pipeline/service
connection permissions. Azure deployment permissions are a separate decision;
repository initialization does not grant them.

Start with an approved local clone of BLUE `release/v1.25` (route A's first clone
command), then use the following in Bash. Replace the organization/project/repository
and `BLUE_SOURCE` paths; `BLUE_SOURCE` is only the source of BLUE's thin adapter,
not the new destination:

```bash
BLUE_SOURCE="/absolute/path/to/blue-v125"
PURPLE_SHA=89eca66185366a702b026cec8c938570548c649c
git clone https://dev.azure.com/YOUR-ORG/YOUR-PROJECT/_git/YOUR-REPO my-aifactory
cd my-aifactory
git switch -c release/v1.25
git submodule add --branch release/v1.25 \
  https://github.com/jostrm/azure-enterprise-scale-ml azure-enterprise-scale-ml
git -C azure-enterprise-scale-ml checkout --detach "$PURPLE_SHA"
git add .gitmodules azure-enterprise-scale-ml
mkdir bootstrap
cp "$BLUE_SOURCE/bootstrap/consumer.py" bootstrap/
cp "$BLUE_SOURCE/01b-BYORepo-init-template-files-once.sh" .
cp "$BLUE_SOURCE/.gitignore" .
cp "$BLUE_SOURCE/.gitattributes" .
bash 01b-BYORepo-init-template-files-once.sh --dry-run
bash 01b-BYORepo-init-template-files-once.sh
# Edit aifactory/variables.json and the ADO variables/variables.yaml before committing.
# This newly created repository contains only the reviewed consumer bootstrap.
# Include generated lib/ui/templates and launcher dependencies, not just YAML.
git status --short
git add .
git diff --cached --stat
git commit -m "Initialize pinned v1.25 AI Factory consumer"
git push -u origin release/v1.25
```

In the new Azure DevOps repository, select `release/v1.25` as the default branch
if that is your approved branch policy. The upstream implementation remains a
submodule; the copied consumer provider YAML and configuration are intended
consumer entry points, not another shared implementation.

Create pipelines through **Pipelines > New pipeline > Azure Repos Git > Existing
Azure Pipelines YAML file**, selecting the release branch. The current paths are:

| Purpose | YAML file under `aifactory/esml-infra/azure-devops/bicep/yaml/` |
|---|---|
| Common infrastructure | `esml-infra-common/infra-aifactory-common.yaml` |
| Unified project infrastructure | `esml-infra-project/infra-project-genai.yaml` |
| AI gateway | `esml-infra-common/infra-ai-gateway.yaml` |
| Dashboards / health model | `esml-infra-project/infra-project-dashboards.yaml` / `infra-project-healthmodel.yaml` |
| Private Azure MCP | `esml-infra-project/infra-project-azure-mcp.yaml` |
| Governance / cross-charging | `aifactory-governance/gov-cross-charging.yaml` |

`infra-project-genai.yaml` is the canonical v1.25 **ADO** filename; unlike GitHub,
it was not renamed to `infra-project.yml`. Keep included `jobs/` and `variables/`
templates together. Review all `azureSubscription` service-connection references,
variable-group references and pool names in the selected pipeline. Create the
named Azure Resource Manager service connections using approved workload identity
federation where supported, authorize only the required pipelines, and configure
Library variable groups/secrets separately. The build identity needs repository
read access, authorized group/connection access, and any project-specific approvals.

Keep recursive submodule checkout on each job that needs PURPLE:

```yaml
steps:
  - checkout: self
    submodules: recursive
```

Runners need network access to the public PURPLE repository; private variants need
approved checkout authentication. Validate agent prerequisites, private network/DNS
reachability and deployment identities separately before running pipelines.
GitHub `.env` synchronization does **not** configure Azure DevOps variable groups,
service connections, secrets or pipelines. Do not execute GitHub sync for this route.

## Configuration and precedence

The supported layout is the upstream **legacy consumer layout** rooted at
`aifactory/variables.json`, with the Azure DevOps variable YAML under
`aifactory/esml-infra/azure-devops/bicep/yaml/variables/`. Do not mix it with the
registered `azurefactory/register.json` layout. Registered factories require
their documented lifecycle tooling rather than these legacy launcher paths.

GitHub environments are `dev`, `stage`, `prod`; the upstream Azure/configuration
environment vocabulary is **dev/test/prod**. In particular, GitHub `stage` supplies
`AZURE_ENV_NAME=test`. Only the environments selected for a synchronization run
are validated or modified.

`.env` is local trusted **data**, not shell code. It supports `KEY=value`,
single/double quotes, spaces and comments; duplicate keys and malformed quotes
fail. No shell substitution, command execution or variable expansion occurs.
Keep `.env.template` tracked with placeholders; `.env` and local variants remain
ignored. Never enable command tracing around credentials or publish local env files.

Repository policy precedence is explicit CLI flags over the local `.env`.
Synchronization resolves environment-specific values before the corresponding
global aliases, as recorded in `bootstrap/github-settings.json`; the same mapping
is used during mirror bootstrap and subsequent updates. Blank, omitted or optional
placeholder values preserve existing GitHub settings. Required selected-environment
values must be real. Omitted secrets are not erased; required omitted secrets on a
configuration-only rerun must already exist remotely. `AZURE_CREDENTIALS` is never
populated with dummy values.

Synchronization writes GitHub settings; it does **not** rewrite consumer JSON/YAML.
Conversely, editing JSON/YAML does not synchronize GitHub. Workflow inputs choose
the upstream configuration mode. Review that mode before deployment: JSON-mode
workflows resolve the selected JSON/project overlays, while GitHub-variable mode
uses the explicitly configured variables. The Azure DevOps templates use their
variable templates/groups and selected configuration source. Do not keep
conflicting values in several sources and assume `.env` automatically wins at
deployment time.

Use `--auth-mode oidc` with separately provisioned workload federation.
`AZURE_CLIENT_ID` and `TENANT_ID` are GitHub **secrets** in the pinned workflow
contract; `AZURE_SUBSCRIPTION_ID` is a variable. Federated subjects use the GitHub
environment name, for example `repo:OWNER/REPO:environment:stage`, not `test`.
The workflows need `id-token: write` and the identity needs explicitly assigned,
least-privilege Azure roles appropriate to the deployment.

The explicit fallback is `--auth-mode credentials` with real environment-specific
`AZURE_CREDENTIALS` JSON containing `clientId`, `clientSecret`, `tenantId` and
`subscriptionId`. Provision and rotate credentials separately, store them securely
and set an expiration. Bootstrap creates neither identities nor credentials.

Pinned upstream authentication is not uniform: its gateway template is
credential-only and its dashboard/health templates are OIDC-only. BLUE applies a
narrow, deterministic authentication adapter when copying these templates:
`AZURE_AUTH_MODE` explicitly selects OIDC or credentials across the installed
workflows, without changing their deployment implementation. Credential mode
overrides preserved stale OIDC secrets; no secrets are deleted. Gateway gains an
OIDC login and dashboard/health workflows gain an explicit credential login.
With the selector absent, each upstream template's original behavior is retained.
Explicit JSON-derived identity mode remains OIDC-only and rejects a conflicting
credential selection. These are BLUE orchestration adaptations, not claims about
unmodified upstream parity; they have not been tested against live Azure identities.

## Initialization, refresh and deployment boundaries

```bash
bash 01b-BYORepo-init-template-files-once.sh --dry-run
bash 01b-BYORepo-init-template-files-once.sh
bash 03b-GH-add-aifactory-pipelines-once.sh --dry-run
bash 03b-GH-add-aifactory-pipelines-once.sh
```

Both entry points resolve their own repository directory and use the selected
submodule, including its non-destructive copier and required `lib/`, `ui/` and
`templates/` helper bundle. They preserve active JSON/YAML, `.env`, the BLUE
variable-sync script and unrelated files. Review refreshed `*-template` files
and merge relevant new defaults into your active configuration yourself.
Conflicting customized copied files require review rather than silent replacement.
Recognized unchanged obsolete BLUE files are retired into ignored private backups
under `.aifactory-backups/`; do not commit or share those backups.

For an empty-ADO consumer containing only the thin Python adapter, the equivalent
refresh command is `python bootstrap/consumer.py refresh --dry-run`, then omit
`--dry-run` only after review. Do not execute PURPLE's older destructive copy
scripts independently of this adapter.

`04ab-setup-infra-aifactory.sh` is now **plan-only by default**:

```bash
bash 04ab-setup-infra-aifactory.sh --repo YOUR-OWNER/YOUR-REPO \
  --ref release/v1.25 --target project --environment dev
```

It reports the current supported workflow command. Only the explicit `--execute`
option dispatches GitHub Actions; that is an Azure deployment operation requiring
separate authorization and completed configuration. Common Stage/Prod orchestration
includes earlier common environments upstream, so the wrapper requires
`--include-common-prerequisites` before expanding that scope. Common defaults to
GitHub environment configuration; `--use-json-config-override` explicitly selects
the upstream JSON/OIDC mode instead.

The wrapper's local plan does not run a workflow. By contrast, the gateway
workflow input `action=plan` is **not** a universal safety guarantee: managed APIM
supports planning, but enabled classic APIM/Kong paths may still deploy. Review
gateway flags and the selected pipeline before dispatch.

## Compatibility matrix

The selected source commit is the evidence baseline; the local architecture graph
was stale and indexed a different revision, so it was not used as release proof.
The detailed surface inventory follows the actual pinned source, not PURPLE main.

In the table, `P` means `azure-enterprise-scale-ml` and `S` means
`P/environment_setup/aifactory/bicep/copy_to_local_settings`.

| Feature/surface | Selected upstream source | BLUE entry point/configuration | Coverage or gap |
|---|---|---|---|
| Non-destructive bootstrap | `P/bootstrap/lib/bootstrap_no_delete.py` and its `initialize_azurefactory.py` dependency | `01b`, `03b`, `bootstrap/consumer.py`; generated `lib/`, `ui/`, `templates/` helpers | Reuses upstream merge/copy support; does not invoke destructive legacy refresh scripts |
| Configuration and release metadata | `P/environment_setup/aifactory/variables.json`; `S/azure-devops/esml-yaml-pipelines/variables/variables.yaml` | `aifactory/variables.json`, `variables-template.json`, ADO variable YAML | New consumer metadata is 1.25 / `release/v1.25`; upstream examples naming 1.24 remain untouched |
| GitHub common/project infrastructure | `S/github-actions/infra-common.yml`, `infra-project.yml`, `infra-project-phase.yml` | Same three files in `.github/workflows`; `04ab` | Replaces obsolete split ESML/GenAI workflows; phase is reusable; BLUE adapts explicit authentication selection only |
| Azure DevOps infrastructure | `S/azure-devops/esml-yaml-pipelines` | `aifactory/esml-infra/azure-devops/bicep/yaml` | Current jobs, variables and dependencies included; canonical ADO project filename remains `infra-project-genai.yaml` |
| AI gateways | `S/ai-gateway`; provider `infra-ai-gateway` templates | `aifactory/ai-gateway`, GitHub/ADO gateway entry points | Optional; BLUE adds explicit OIDC to the credential-only GitHub source; managed-APIM planning is not a universal no-write gateway mode |
| Dashboards and health model | `S/github-actions/infra-project-dashboards.yml`, `infra-project-healthmodel.yml`; corresponding ADO templates | Matching active workflows/pipelines | Available; BLUE adds explicit credential fallback to the OIDC-only GitHub sources |
| Automation, private MCP and factory agent | `S/automation`, ADO project/MCP/agent jobs; `P/usecase_code/40-agent-factory` | `aifactory/automation`, ADO provider jobs, selected upstream feature flags | Available through submodule/provider templates; no invented GitHub/ADO parity or automatic hosting |
| Governance and personas | `S/azure-devops/esml-yaml-pipelines/aifactory-governance`; `P/environment_setup/aifactory/bicep/personas/cli.py` | Copied governance pipeline and upstream persona CLI | Existing permission/review boundaries remain; availability is not approval to execute |
| Factory CLI / SDK | `P/environment_setup/azurefactory-cli/src/azurefactory/__main__.py` and `client.py` | Consume pinned CLI package against a separately configured Factory API | No duplicated BLUE API/client implementation; API authentication and deployment are separate |
| Factory API / configuration wizard | `P/environment_setup/install_config_wizard`, including `release-manifest.json` and `api-usage-examples` | Upstream distribution and examples | API implementation/distribution is external; not a new server implemented in BLUE |
| Agent Factory | `P/usecase_code/40-agent-factory/agent_factory/__main__.py`; `40-aifactory-agent/aifactory_agent/__main__.py` | Use pinned packages, per-usecase configuration and instructions | Runtime/deployment validation not performed |
| ML Factory | `P/usecase_code/50-ml-model-factory/accelerator/src/ml_model_factory/__main__.py` | Pinned ML accelerator and templates | Release path is **50-ml-model-factory**, not main's newer 50-ml-factory; upstream records limited tested implementations, not blanket runtime validation |
| Registered factory lifecycle | `P/01-start-v125-and-above.sh`, `P/bootstrap/lib/factory_lifecycle.py` | Separate migration/new registered repository only | Not mixed into this legacy consumer; `azurefactory/register.json` roots are rejected by the BLUE adapter |
| Historical copied utilities | Legacy BLUE `parameters`, util/classic/Terraform/dashboard and member-workflow copies | Replaced by current configuration and direct upstream paths | Migration retires only recognized unchanged baseline files; customized obsolete files require review rather than deletion |

Detailed pinned documentation: [Factory CLI](https://github.com/jostrm/azure-enterprise-scale-ml/blob/89eca66185366a702b026cec8c938570548c649c/environment_setup/azurefactory-cli/readme.md),
[API distribution and configuration wizard](https://github.com/jostrm/azure-enterprise-scale-ml/blob/89eca66185366a702b026cec8c938570548c649c/environment_setup/install_config_wizard/readme.md),
[Agent Factory](https://github.com/jostrm/azure-enterprise-scale-ml/blob/89eca66185366a702b026cec8c938570548c649c/usecase_code/40-agent-factory/readme.md),
[ML Factory](https://github.com/jostrm/azure-enterprise-scale-ml/blob/89eca66185366a702b026cec8c938570548c649c/usecase_code/50-ml-model-factory/readme.md).

Availability through the submodule does not establish that the external Factory
API, agent, model, infrastructure or optional service has been deployed or tested
in your tenant. Optional capabilities are not all enabled by bootstrap.

## Upgrading an existing BLUE consumer

The prior published BLUE release branch is `release/v1.24`; no public release tag
was present at inspection. Preserve your edits and `.env` before upgrading.
Never use mirror bootstrap as an upgrade mechanism.

Review the v1.25 branch changes separately from your consumer configuration,
especially the replacement of old `aifactory/parameters` files and split ESML/GenAI
workflow entry points. Migrate actual values deliberately; do not overwrite
consumer settings with example defaults.

For a future upstream upgrade, select and review exactly one commit, update the
gitlink deliberately, refresh templates non-destructively, run consumer tests,
review the complete diff, and commit configuration/template changes together:

```bash
git -C azure-enterprise-scale-ml fetch origin release/v1.25
# Review origin/release/v1.25, then replace REVIEWED_FULL_SHA below with its selected SHA.
git -C azure-enterprise-scale-ml checkout --detach REVIEWED_FULL_SHA
git add .gitmodules azure-enterprise-scale-ml
git diff --cached --submodule=log
```

Do not silently reselect a newer SHA mid-upgrade. Review the release metadata and
mapping/source contracts at the same time. The v1.25 BLUE adapter intentionally
accepts only this reviewed pin; a future pin also requires the matching reviewed
BLUE adapter `PIN`, mapping `upstream_commit`, source-contract tests and release
metadata update (prefer a compatible BLUE release), not just an isolated
submodule checkout. A disabled feature flag may leave
existing resources, data and charges in place; deletion is a separately governed
lifecycle operation.

## Validation and release publication

The `bootstrap-consumer-tests.yml` workflow runs on relevant pushes and pull
requests targeting `release/v1.25`. It separates mocked unit/source-contract tests
from real disposable local-Git tests on Linux and Windows Git Bash. Tests do not
need Azure credentials, production secrets or a remote write destination.

Manual dispatch is declared, but BLUE's unchanged `main` does not contain this
new workflow. Until a separately approved default-branch change, use the **push**
trigger on `release/v1.25` for BLUE release evidence. Generated consumers with the
release selected as default can use manual dispatch normally.

After committing and pushing the final release branch, bind publication to the
exact successful push run:

```bash
BLUE_SHA=$(git rev-parse HEAD)
python bootstrap/release_evidence.py \
  --repo Azure/enterprise-scale-aifactory --sha "$BLUE_SHA"
```

The read-only command returns `headSha`, the run URL/ID and both successful platform
jobs. It rejects a different SHA, a pull-request merge run, a different workflow,
missing jobs or failed/pending evidence. If access is blocked by SSO or repository
policy, preserve local work and resolve authorization; do not bypass policy.

Inspect remote branch, tag and release before any publication. Never move an
existing `release_125` tag or overwrite unrelated release notes. Once the exact
commit has required successful checks, an authorized maintainer can run:

```bash
git tag -a release_125 "$BLUE_SHA" -m "Release v1.25"
git push origin refs/tags/release_125
gh release create release_125 --repo Azure/enterprise-scale-aifactory \
  --verify-tag --target release/v1.25 --title "Release v1.25" \
  --notes-file bootstrap/release-notes.txt --latest=false
```

This is a normal release, not a draft or prerelease, and does not request the
latest designation or change the default branch. Repository/bootstrap validation
is not Azure deployment validation: no Azure deployment is authorized or claimed.
