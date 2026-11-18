# BLUE v1.25+ registered consumer onboarding

BLUE supports **v1.25 and newer only**, using `azurefactory/register.json`.
It does not initialize, migrate into, refresh or deploy the legacy `aifactory/`
configuration layout. Both configuration folders are not required.

[Full setup & usage guide](https://github.com/jostrm/azure-enterprise-scale-ml/blob/release/v1.25/documentation/v2/20-29/24-end-2-end-setup.md) |
[Full variable documentation](https://jostrm.github.io/azure-enterprise-scale-ml/)

PURPLE supplies the versioned implementation. BLUE selects
`release/v1.25` at **`89eca66185366a702b026cec8c938570548c649c`**. The full guide
tracks the upstream release branch; implementation references and compatibility
evidence below remain pinned to that exact commit. Reading the guide does not
update the submodule or select a later source revision.
The variable documentation site is maintained independently; confirm parameter
availability against the selected source and installed API.
Repository bootstrap does not deploy Azure, create identities or credentials,
configure API connections, register pipelines or launch an editor.

## Prerequisites and immutable source

Use Git, Bash and Python 3.10+; on Windows, Git for Windows **Git Bash** and a real
Python interpreter, not a Windows Store alias. Scripted GitHub operations additionally
need GitHub CLI authentication, destination-repository administration permission,
workflow permission where required, and organization SAML SSO authorization.
SSH needs an authorized key; HTTPS uses your credential manager. Never embed
credentials in remote URLs.

Some pinned upstream notebook paths exceed Windows MAX_PATH. Use
`git -c core.longpaths=true clone ...` for initial cloning and
`git -c core.longpaths=true submodule update --init --recursive` when repairing.
BLUE's CI supplies the same setting through job-scoped Git configuration before
recursive checkout, without changing your system-wide Git settings.

`.gitmodules` declares `branch = release/v1.25`. That metadata selects the branch
for **explicit updates**; ordinary recursive clones reproduce the **committed
gitlink**. Bootstrap never follows `main`, uses `--remote`, or silently selects a
new release tip. Supporting later releases requires a reviewed compatible BLUE
update, not an automatic claim that unknown future contracts work.

## A. GitHub mirror

```bash
git -c core.longpaths=true clone --branch release/v1.25 --recurse-submodules \
  https://github.com/Azure/enterprise-scale-aifactory.git blue-v125
cd blue-v125
cp .env.template .env
```

Edit `.env` with explicit repository policy and the selected GitHub environments.
The repository settings are `GITHUB_SOURCE_REPO`, `GITHUB_SOURCE_BRANCH`,
`GITHUB_DESTINATION_REPO`, `GITHUB_VISIBILITY`, `GITHUB_DESTINATION_STATE`,
`GITHUB_DEFAULT_BRANCH`, `GITHUB_TRANSPORT`, `GITHUB_ENVIRONMENTS` and
`GITHUB_AUTH_MODE`. Then preview and apply:

```bash
bash 01a-GH-mirror-repo-from-template-once.sh --dry-run
bash 01a-GH-mirror-repo-from-template-once.sh
```

Explicit CLI flags override the local `.env`, for example:

```bash
bash 01a-GH-mirror-repo-from-template-once.sh \
  --source Azure/enterprise-scale-aifactory --source-branch release/v1.25 \
  --destination YOUR-OWNER/YOUR-REPO --visibility private \
  --destination-state create --default-branch release/v1.25 \
  --transport https --environments dev --auth-mode oidc --env-file .env --dry-run
```

`create` explicitly requests a new repository. `existing-empty` requires an
already-created empty repository. Source=destination, nonempty refs, failed
authentication, unconfirmed permissions and ambiguous API errors stop the
operation. HTTP 404 is not proof that a repository is safe to overwrite.
Organization creation conservatively requires owner/admin membership; otherwise
have an authorized owner create an empty repository and use `existing-empty`.

This is a **full mirror**, not a release-only copy:
`git clone --mirror` then `git push --mirror --atomic` preserves advertised refs
and their history. Historical branches can therefore exist in the mirror, but
BLUE's selected/default consumer branch must be v1.25+; they are not supported
execution routes. Do not initialize a destination README or allow concurrent
writers during bootstrap. Server-owned refs or policy may reject the mirror;
there is no force-push, filtered-ref or history-replacement fallback.

A mirror does **not** copy repository settings, environment protection,
variables or secrets. After the Git push, the script selects the requested
release as the **destination** default branch and synchronizes only the selected
GitHub environment settings. Configure approvals, branch rules and federation
separately. BLUE's own default branch is unchanged.

The script only removes its own temporary bare clone, never an existing consumer
checkout. Clone the destination and initialize its registered helper bundle:

```bash
git -c core.longpaths=true clone --branch release/v1.25 --recurse-submodules \
  https://github.com/YOUR-OWNER/YOUR-REPO.git my-aifactory
cd my-aifactory
bash 01b-BYORepo-init-template-files-once.sh --provider gha
```

Initialization installs the manual-only scoped provider workflow locally. Review
and publish it in **your consumer** before preparing a provider operation:

```bash
git diff -- .github/workflows/factory-lifecycle.yml
git status --short
git add .github/workflows/factory-lifecycle.yml azurefactory
git commit -m "Install pinned registered GitHub lifecycle entry point"
git push origin release/v1.25
```

The empty catalog may already be tracked; skip a no-change commit on reruns.
The helper/SDK bundle is reproducible from the gitlink; run `01b` in each new
local clone instead of treating generated local caches as a second implementation.

For subsequent GitHub settings changes, copy/edit `.env.template` in the consumer
and use **configuration-only** synchronization:

```bash
bash 02b-GH-create-or-update-github-variables.sh --dry-run
bash 02b-GH-create-or-update-github-variables.sh
```

This never clones, pushes, creates a repository or changes its default branch.
Failures return nonzero and report partial completion without rollback/deletion.
If GitHub accepted some writes, inspect the destination before retrying. Never
rerun mirror creation against the now-populated repository.

## B. GitHub Use this template

### How to use the "Use this template" button

**Use this template** creates an independent repository with a fresh history.
It is a starting point for the same registered consumer setup as the mirror
route, not a full Git mirror or an Azure deployment.

**Repository state checked on 2026-11-18:** template mode is enabled
(`is_template=true`) and the default branch is `main`. The current `main` and
`release/v1.25` have the same bootstrap scripts, `.gitmodules` and common
functionality gitlink. The steps below deliberately select `release/v1.25`;
they do not certify every other branch that GitHub may copy.

1. Sign in to GitHub and open [this repo](https://github.com/Azure/enterprise-scale-aifactory). You need permission to create a repository under your chosen account or organization.
2. At the top right above the files, select **Use this template > Create a new repository**. **Open in a codespace** is a different route: it starts a development environment, not this completed repository-creation flow.
3. Select the **Owner**, enter a unique repository name such as `my-aifactory`, and choose the visibility your organization permits. Prefer **Private** for customer configuration; never put credentials in the description or tracked files.
4. Select **Include all branches** to obtain the named `release/v1.25` branch used by this guide. GitHub offers the source's default branch or all branches, not an arbitrary branch selected in the source page's branch dropdown.
5. Select **Create repository from template** and wait for the files and branches to appear in your new repository. This creates a repository, not identities, runners or Azure resources.
6. In **your new repository**, select `release/v1.25`. Set it as the default branch under **Settings > General > Default branch**, or use the CLI command below. This requires destination administration permission and does not change this source repo's default branch.

**Default-only is an option, but is different:** omitting **Include all branches**
copies the current `main` snapshot, which currently contains the v1.25 consumer
implementation; it is not an older legacy bootstrap. It does not create the
named `release/v1.25` branch used by the recipe below. Use the all-branches route
for this release-based walkthrough. Copying all branches also includes historical
and other release branches; their presence does not make them supported here.

If the button is missing, confirm you are signed in, viewing the source repository
and permitted to create a destination. A source administrator can inspect the
**Template repository** setting; there is no need to change the source default
branch or bypass organization policy.

### CLI alternative to clicking the button

The following is equivalent to creating a private template-derived repository
with all branches. **Skip this command if you already created it in the browser.**
It is template generation, not the programmatic mirror script:

```bash
gh repo create YOUR-OWNER/YOUR-REPO \
  --template Azure/enterprise-scale-aifactory --include-all-branches --private
```

### After creation: clone and initialize the common functionality

Use the prerequisites above, including Git Bash on Windows. Replace
`YOUR-OWNER/YOUR-REPO` with the **new destination**, not this source repository:

```bash
git -c core.longpaths=true clone --branch release/v1.25 \
  https://github.com/YOUR-OWNER/YOUR-REPO.git my-aifactory
cd my-aifactory
gh repo edit YOUR-OWNER/YOUR-REPO --default-branch release/v1.25
git ls-tree HEAD azure-enterprise-scale-ml
git config --file .gitmodules --get submodule.azure-enterprise-scale-ml.branch
git config --file .gitmodules --get submodule.azure-enterprise-scale-ml.url
```

The selected source records mode `160000` (a Git submodule reference), commit
`89eca66185366a702b026cec8c938570548c649c`, branch `release/v1.25`, and URL
`https://github.com/jostrm/azure-enterprise-scale-ml`. The submodule is a reference
to the common functionality, not a vendored copy of that entire repository.
If registration is missing, use the repair subsection before initialization.
If the recorded version differs, review the source and adapter compatibility
rather than substituting the latest branch tip.

With the expected registration present:

```bash
git -c core.longpaths=true submodule update --init --recursive
git -C azure-enterprise-scale-ml rev-parse HEAD
bash 01b-BYORepo-init-template-files-once.sh --provider gha --dry-run
bash 01b-BYORepo-init-template-files-once.sh --provider gha
```

The initialized source should report the recorded commit, not a later release
tip. Initialization installs the empty `azurefactory/register.json`, the helper
bundle and the manual-only `.github/workflows/factory-lifecycle.yml`.
As in [route A](#a-github-mirror), review, commit and push that workflow and the
register in **your consumer** before using the scoped provider. A compatible
Factory API is still required to configure the catalog; this step does not deploy.

### If template generation omitted the submodule registration

Do not assume that copying `.gitmodules` alone proves the gitlink survived.
The existing initializer has an explicit local repair path for missing metadata
or a missing gitlink. In Git Bash, the process-scoped long-path settings below
also cover Git calls made by the initializer on Windows:

```bash
export GIT_CONFIG_COUNT=1 GIT_CONFIG_KEY_0=core.longpaths GIT_CONFIG_VALUE_0=true
bash 01b-BYORepo-init-template-files-once.sh --repair-submodule --dry-run
bash 01b-BYORepo-init-template-files-once.sh --repair-submodule --provider gha
git diff --cached --submodule=log
git add .gitmodules azure-enterprise-scale-ml
git commit -m "Restore pinned v1.25 shared implementation"
git push origin release/v1.25
```

Repair refuses populated untracked source paths, conflicting pins and modified
source. It neither deletes them nor commits/pushes automatically.
Preserve conflicting local work for review rather than deleting it. After repair,
also publish the generated workflow and register as described above; the repair
commit alone only records the submodule.

### Configure the new repository, not another mirror

Neither template generation nor a Git mirror copies the source's secrets,
environment protection, branch rules, collaborators, issues, pull requests or
GitHub release assets. Tracked workflow files are copied, but credentials,
runner access and policy must be configured for the destination.

For a newly created consumer, copy `.env.template` to `.env`. If `.env` already
exists, edit it instead of overwriting it. Set `GITHUB_DESTINATION_REPO` to
`YOUR-OWNER/YOUR-REPO`, choose `GITHUB_ENVIRONMENTS` and the explicit
`GITHUB_AUTH_MODE=oidc`, and provide the selected authentication values described
in [GitHub settings and precedence](#github-settings-and-precedence).
Then preview and apply **configuration-only** synchronization:

```bash
bash 02b-GH-create-or-update-github-variables.sh --dry-run
bash 02b-GH-create-or-update-github-variables.sh
```

This configures selected GitHub environment values; it does not install
workflows, create Azure identities or OIDC federation, bind pipelines, or
configure the Factory API. Configure those separately, plus required approvals,
branch protection and runner access. Organization policy and your GitHub plan
must permit the selected repository visibility and environment features.

`workflow_dispatch` discovery requires the workflow on the **destination default
branch**. Publish it on the selected `release/v1.25` default branch instead of
merging generated branches; supplying `--ref` alone is not a substitute.

### Template versus programmatic mirror: pros and cons

Both routes can reach the same registered consumer layout, common functionality
pin and manually reviewed lifecycle. Their Git provenance and setup automation
are different. The mirror below specifically means this repo's
`01a-GH-mirror-repo-from-template-once.sh`, not just a generic `git clone`.

| Consideration | Use this template | Programmatic mirror (`01a`) |
|---|---|---|
| Best fit / main advantage | Quick browser-led start with a clean history for a new independent project. CLI template generation is also available. | Repeatable, policy-explicit bootstrap when retaining source provenance, branches and tags matters. |
| History and branches | Starts with a single commit per generated branch. All-branches generation creates unrelated histories; generated branches cannot be merged or compared in normal pull requests as shared-history branches. Not a history/tag backup. | Preserves advertised Git refs, tags, commit IDs and history, including branch ancestry, through `git clone --mirror` and `git push --mirror --atomic`. |
| Release selection | Default branch snapshot or all branch snapshots. Choose all branches and then `release/v1.25` for this guide; set the destination default yourself. | Requires an explicit v1.25+ source release and sets that as the destination default. Despite `--source-branch`, it mirrors **all refs**, not only that release. |
| Destination and permissions | Creates a new repository; cannot fill an existing empty repository. Browser creation needs no local CLI. Organization creation policy still applies; later settings require appropriate administration rights. | Explicit `create` or `existing-empty` destination; Git, Bash, Python, authenticated `gh` and Git transport required. The script requires destination admin/push permission; organization creation conservatively requires owner/admin membership. |
| Common functionality submodule | Inspect metadata and gitlink after generation; initialize recursively, or use explicit repair if missing. The common functionality repository is not copied into your ownership. | Git history preserves the gitlink and `.gitmodules`; you still initialize recursively and need access to the common functionality. Its repository is not separately mirrored. |
| GitHub environments / OIDC | Separate step: configure the local `.env`, then run `02b` after creation. No source secrets or settings are inherited. | After the mirror, writes only the selected environment variables/secrets from the supplied local `.env`; it does not copy source secrets or protections. Initial authentication values are required even for `--dry-run`. |
| Safety and failure handling | No mirror push against an existing destination, but no equivalent scripted end-to-end preflight. Complete the branch, submodule and settings steps explicitly. | Read-only `--dry-run`, identity/permission checks and repeated empty-destination checks. Ref/policy rejection stops the operation; inspect partial results before retrying. No destructive overwrite fallback. |
| Trade-offs / disadvantages | Fresh ancestry loses original commit audit history. All-branches snapshots are awkward for cross-branch development; create future feature branches from your chosen consumer branch instead. | Transfers more history, including historical/unwanted content; review it before copying. Server-owned refs or organization rules can reject the all-ref push. |
| Later updates | Changes in this source repo do **not automatically** update the generated consumer. Review and port bootstrap changes deliberately; update the common functionality pin through the reviewed upgrade path. | One-time bootstrap, **not automatically** an ongoing synchronization service. Shared ancestry can help deliberate Git updates, but never rerun `01a` against a populated destination. |
| GitHub metadata / Git LFS | Not a settings, issue or release-asset migration. GitHub templates do not support files stored using Git LFS. | Git refs are not GitHub settings or release assets. This script has no `git lfs fetch/push --all` phase; if LFS is introduced, Git mirroring alone is insufficient to migrate its objects. |

**Recommendation:** use the button for a fresh independent project when you do
not need the source's commit history. Use the programmatic mirror when history
and repeatable environment setup are requirements and you accept its additional
tooling and permission prerequisites. Neither is a one-click Azure deployment.
**Never run the mirror script against a template-created repository**: it already
contains commits, so it is intentionally rejected. Use `02b` for settings only.

### Evidence and limits

GitHub's documented template behavior, the enabled source setting and current
source branches were inspected on **2026-11-18**. The native generation service
was **not tested** by creating a new GitHub repository during this documentation
work; preserving a gitlink on a newly generated destination remains something
to inspect, not a claimed live result. No destination repository, credentials or
Azure resources were created for this investigation.

The implementation evidence is
[`bootstrap/github_bootstrap.py`](../bootstrap/github_bootstrap.py)
(`mirror_git`, `execute`, `sync_settings`) and
[`bootstrap/consumer.py`](../bootstrap/consumer.py)
(`repair_submodule`, `ensure_submodule`). Existing local-Git tests in
[`tests/test_mirror_git.py`](../tests/test_mirror_git.py) cover actual ref/history
copying and refusal of populated destinations; selected tests in
[`tests/test_consumer_git.py`](../tests/test_consumer_git.py) cover recursive
initialization, explicit missing-registration repair and preservation of local
files. These support the local path, not GitHub-hosted generation or Azure deployment.

References: [GitHub template generation](https://docs.github.com/en/repositories/creating-and-managing-repositories/creating-a-repository-from-a-template),
[template limitations](https://docs.github.com/en/repositories/creating-and-managing-repositories/creating-a-template-repository),
[GitHub CLI template creation](https://cli.github.com/manual/gh_repo_create),
[Git mirroring and LFS](https://docs.github.com/en/repositories/creating-and-managing-repositories/duplicating-a-repository),
and [manual workflow discovery](https://docs.github.com/en/actions/how-tos/manage-workflow-runs/manually-run-a-workflow).

## C. Empty Azure DevOps or bring your own repository

Create an empty Azure DevOps Git repository through **Repos > repository selector >
New repository > Git**, without a README. Use normal Git Credential Manager or
approved SSH authentication, never a token in the URL. You need repository
Read/Contribute/Create branch and, if creating it, Create repository permission.

Use an approved local BLUE `release/v1.25` checkout as `BLUE_SOURCE`. The following
initializes local registered configuration and helpers only:

```bash
BLUE_SOURCE="/absolute/path/to/blue-v125"
PURPLE_SHA=89eca66185366a702b026cec8c938570548c649c
git clone https://dev.azure.com/YOUR-ORG/YOUR-PROJECT/_git/YOUR-REPO my-aifactory
cd my-aifactory
git switch -c release/v1.25
git -c core.longpaths=true submodule add --branch release/v1.25 \
  https://github.com/jostrm/azure-enterprise-scale-ml azure-enterprise-scale-ml
git -C azure-enterprise-scale-ml -c core.longpaths=true checkout --detach "$PURPLE_SHA"
git add .gitmodules azure-enterprise-scale-ml
mkdir bootstrap
cp "$BLUE_SOURCE/bootstrap/consumer.py" bootstrap/
cp "$BLUE_SOURCE/01b-BYORepo-init-template-files-once.sh" .
cp "$BLUE_SOURCE/.gitignore" .
cp "$BLUE_SOURCE/.gitattributes" .
bash 01b-BYORepo-init-template-files-once.sh --provider ado --dry-run
bash 01b-BYORepo-init-template-files-once.sh --provider ado
git status --short
# Review the empty register and required generated helper bundle; no credentials.
git add .
git diff --cached --stat
git commit -m "Initialize pinned v1.25 registered consumer"
git push -u origin release/v1.25
```

Set the new repository's default branch according to your approved policy.
`ADO-azurefactory.sh` is a scoped lifecycle wrapper, not a pipeline registration.
Use an authorized Factory API to configure the catalog, select bindings and
prepare operations; GitHub `.env` synchronization does **not** configure ADO
service connections, variable groups, secrets or pipelines.

**Pinned ADO limitation:** `bootstrap/templates/factory-lifecycle-ado.yml` is the
registered scoped provider template, but the selected upstream runtime hardcodes
its consumer location as `aifactory/pipelines/factory-lifecycle.yml`. Upstream's
registered installer rejects any consumer-root `aifactory` directory. BLUE does
not recreate that conflicting folder or pretend `azurefactory/pipelines` is an
accepted replacement. Local ADO registered initialization is supported; end-to-end
scoped ADO publication/execution requires a separately reviewed upstream contract
correction and a compatible pin before it is advertised as ready in this repo.

When that upstream prerequisite is resolved, register the approved template via
**Pipelines > New pipeline > Azure Repos Git > Existing Azure Pipelines YAML file**,
using the runtime's accepted path and reviewed commit. Create an approved
workload-identity-federated Azure Resource Manager service connection; authorize
only the selected pipeline, runner and variable groups. The runtime supplies the
protected execution envelope; do not put it in `.env`, Git or generic variables.
Required permissions include pipeline creation, service-connection authorization,
repository read, approved variable-group access and deployment-specific Azure roles.

For ordinary repository checkout, use:

```yaml
steps:
  - checkout: self
    submodules: recursive
```

The pinned scoped provider template uses `submodules: true` and is subject to an
exact-source check; do not silently edit it to pass a setup guide. Private runners
also need the documented compiler, network/DNS access and authenticated submodule
access where applicable. None of those resources is provisioned by this guide.

## Registered configuration and safe refresh

BLUE delegates to the implementation behind PURPLE's
`01-start-v125-and-above.sh`: **`bootstrap/lib/registered_setup.py`**. It installs
the upstream registered shell wrappers, supporting `lib/`, `ui/`, register
template and `.azurefactory-tools/` SDK/CLI/persona bundle. Those dependencies
are required; copying a root launcher by itself is insufficient.

```bash
bash 01b-BYORepo-init-template-files-once.sh --dry-run
bash 01b-BYORepo-init-template-files-once.sh
bash 03b-GH-add-aifactory-pipelines-once.sh --dry-run
bash 03b-GH-add-aifactory-pipelines-once.sh
```

Both use the reviewed pin and operate relative to the consumer, not the caller's
working directory. The old `03b` filename now means registered helper/provider
refresh, not installation of legacy `infra-*` workflows. `04ab` no longer
dispatches legacy infrastructure workflows; use the registered API review path.
`--provider ado|gha|both` selects provider support. Reruns preserve the registered
catalog, generated configuration projections, `.env`, existing secrets and
unrelated consumer files. Do not use shared legacy copy/update scripts as a fallback.

The initial `azurefactory/register.json` contains **zero factories**, empty
configuration and bindings, and no fabricated tenant, subscription or project.
A populated register is validated and preserved, not reset to an example.
The API is the writer of factory/scale-set/project configuration and its readable
projections. `.azurefactory/` metadata (locks, SQLite operations database), private
backups and receipts must remain ignored and must never be published.

### Factory API and CLI

An API is required for catalog configuration; a GUI is not. After initialization:

```bash
bash ./azurefactory.sh api instructions
# Start your approved compatible Factory API separately; no server is started here.
# Supply AIFACTORY_API_KEY privately and the authorized AIFACTORY_API_URL.
bash ./azurefactory.sh health
bash ./azurefactory.sh doctor
bash ./azurefactory.sh factory create --help
```

On Windows, if the upstream launcher selects an unusable Python Store alias, set
`AIFACTORY_PYTHON` to the absolute path of your approved Python interpreter.
The API folder argument is the absolute **API-host** `azurefactory` directory,
not the consumer root; remote clients must not supply a laptop-only path.

Follow the [Full setup & usage guide](https://github.com/jostrm/azure-enterprise-scale-ml/blob/release/v1.25/documentation/v2/20-29/24-end-2-end-setup.md).
Explicitly select version `125`; do not accept a default `main` or `124`.
The helper gitlink and the factory's runtime version selection are distinct:
inspect the prepared operation's resolved source SHA and require this reviewed
commit, not an upstream tip that moved during setup. A later source needs a new review.

Factory creation previews may include the default initial project001. Confirmation
saves approved configuration; it is not an Azure deployment. Bindings, federation,
private runner readiness, runtime preparation and execution require their own
review and authorization. BLUE does not bypass unsupported API capabilities.

### GitHub settings and precedence

The single mapping in `bootstrap/github-settings.json` is used by mirror bootstrap
and subsequent sync. Only the selected GitHub environments are validated/changed.
The `.env` file is trusted **data**, not shell code: quotes, spaces and comments
are supported; duplicates and malformed values fail; shell expansion is never run.
The default `.env` is beside the scripts; explicit `--env-file` is caller-relative.
CLI policy overrides `.env`; environment-specific values override global aliases.
Blank/omitted secrets preserve existing secrets, whose presence is checked when
required. `.env.template` contains placeholders and is tracked; `.env` variants
are ignored. No automatic editor, dummy credential or secret deletion is used.

The pinned **registered GitHub lifecycle requires OIDC**:
`secrets.AZURE_CLIENT_ID`, `secrets.TENANT_ID`, and
`vars.AZURE_SUBSCRIPTION_ID`. `AZURE_CREDENTIALS` credential fallback is **not
supported** by this scoped provider contract and is rejected, not written with
placeholder values or wired into a competing workflow. Provision federated
identities separately. The federated subject's environment must match the
reviewed route's `auth_namespace`, for example
`repo:OWNER/REPO:environment:stage`.

Logical selectors are `dev/stage/prod`, while factory runtime environment names
are **dev/test/prod**. `{ENV}_GITHUB_ENVIRONMENT` can explicitly name the exact
reviewed provider namespace (defaults to the selector's name); selected namespaces
must be distinct. The reviewed binding must map GitHub `stage` to Azure `test`;
`.env` synchronization cannot create that catalog binding automatically.
The protected plan envelope is produced by the lifecycle runtime, not by `.env`.
Factory feature flags, naming, networks and project settings belong in the
registered catalog/API, not the old global `aifactory/variables.json` or a table
of legacy GitHub deployment variables.

These are separate ownership scopes: `.env` synchronizes GitHub authentication
settings; the API owns registered configuration; the reviewed runtime owns frozen
deployment inputs. Neither silently overrides the others.

The advanced `oidc-single-writer` synchronization mode targets the separately
reviewed `factory-lifecycle-single-writer-gha.yml` contract: it writes public
`AZURE_CLIENT_ID`, `AZURE_TENANT_ID` and `AZURE_SUBSCRIPTION_ID` variables and
requires a private repository. It does **not** install/switch the workflow,
enroll a coordination store or change the factory's coordination mode. BLUE's
ordinary scoped workflow uses `oidc`, not this advanced mode. API-generated
workflows must be checked against the installed backend before either mode is used.
The authentication mode is deliberately explicit; there is no implicit default.

The old infrastructure `.env` keys are not silently mapped into registered
configuration. Unsupported keys fail before remote changes; start from the new
template and retain your previous private file separately for reviewed migration.

## Compatibility matrix

`P` below is the pinned `azure-enterprise-scale-ml`. The local architecture graph
was stale and indexed a different revision; direct selected-source inspection is
the compatibility evidence, not graph freshness or deployment proof.

| Surface | Upstream source | BLUE entry/configuration | Coverage or gap |
|---|---|---|---|
| Registered initialization | `P/01-start-v125-and-above.sh`, `bootstrap/lib/registered_setup.py`, `initialize_azurefactory.py` | `01b`, `bootstrap/consumer.py`, `azurefactory/register.json` | Empty register, complete helper bundle, no legacy consumer or deployment |
| Safe helper refresh | Same registered installer; `bootstrap_no_delete.Merge` | `03b`, `--provider` selection | Existing catalog/projections preserved; no competing BLUE catalog writer |
| Configuration and lifecycle | `P/bootstrap/azurefactory.sh`, `environment_setup/azurefactory-cli` | Generated `.azurefactory-tools`, `azurefactory.sh`, provider wrappers | API required; creation/configuration/confirmation distinct from execution |
| GitHub scoped provider | `P/bootstrap/templates/factory-lifecycle-gha.yml` | `.github/workflows/factory-lifecycle.yml` | Manual-only, OIDC, protected reviewed plan; exact upstream template, not legacy infra workflows |
| Azure DevOps scoped provider | `P/bootstrap/templates/factory-lifecycle-ado.yml`; `factory_lifecycle.py::SCOPED_ADO` | Registered ADO wrapper/CLI | Local initialization works; conflicting upstream fixed `aifactory/pipelines` location blocks a no-legacy end-to-end provider install at this pin |
| Gateway, dashboards, health model, governance/personas | `P/environment_setup/aifactory`, registered CLI/settings and lifecycle helpers | Registered project settings and supported reviewed runtime operations | Available source is not proof every operation is exposed/executable by the installed API; no copied legacy pipeline dispatch |
| Agent Factory | `P/usecase_code/40-agent-factory` | Pinned Agent Factory packages/usecases and registered project configuration | Shared implementation only; runtime/deployment validation separate |
| ML Factory | `P/usecase_code/50-ml-model-factory` | Pinned ML accelerator/templates and registered project configuration | Correct release path; main's renamed path and broader test claims are not imported |
| Factory API / wizard | `P/environment_setup/install_config_wizard`, `api-usage-examples` | Separately approved API distribution | Backend is external; BLUE installs a client, not another API server |
| v1.24 / legacy consumers | Historical releases | Not supported by this BLUE branch | No automatic folder rename, legacy refresh or fallback |

The selected source also documents a blocked **integrated access-hub** combination
(`access_hub_mode=integrated`, `setup_hub_access=true`). Configuration can be saved
without making deployment executable. Do not silently substitute an external/no-hub
topology or bypass source guards. Read the
[pinned limitation](https://github.com/jostrm/azure-enterprise-scale-ml/blob/89eca66185366a702b026cec8c938570548c649c/documentation/v2/20-29/24-end-2-end-setup.md#current-integrated-hub-limitation).

## Upgrades and existing legacy consumers

This branch does not support v1.24 or older. Preserve any existing legacy
`aifactory` checkout separately and follow an explicitly reviewed upstream API
migration; do not rename the folder or copy an empty register over real data.
If you pulled the earlier provisional BLUE v1.25 legacy implementation, preserve
all local edits and start this corrected registered consumer separately. Bootstrap
refuses an existing root `aifactory` rather than deleting or converting it.

For later v1.25+ updates, review a compatible BLUE release, select one exact PURPLE
commit and deliberately update/commit the gitlink with matching adapter/mapping
metadata and tests. Fetching alone is safe; checking out a later source does not
make it compatible or migrate the catalog:

```bash
git -C azure-enterprise-scale-ml fetch origin release/v1.25
# Review before selecting a new immutable source and matching BLUE update.
git diff --submodule=log
```

Never rerun full mirror against a populated destination. Feature flags do not
guarantee resource deletion or eliminate ongoing costs; deletion is a separately
reviewed lifecycle operation with retention/ownership rules.

## Validation and release publication

`bootstrap-consumer-tests.yml` runs mocked/source-contract tests and disposable
local-Git integration tests on Linux and Windows Git Bash, with no Azure credentials
or deployment. Windows long-path handling is active before recursive checkout.
Relevant automatic pushes and pull requests target `release/v1.25`, not `main`.
The workflow is also present on the current default `main`, so manual dispatch
can be discovered; select the intended ref explicitly. Release evidence should
still use the exact release-branch push run required by the evidence helper.

For the exact final commit:

```bash
BLUE_SHA=$(git rev-parse HEAD)
python bootstrap/release_evidence.py \
  --repo Azure/enterprise-scale-aifactory --sha "$BLUE_SHA"
```

The read-only command returns `headSha`, run URL/ID and both successful platform
jobs. Different SHA, workflow, PR merge run, failed/pending or missing jobs are
not accepted as release evidence.

Only when separately authorized, after inspecting existing branch/tag/release and
successful required checks, publish without moving an existing tag:

```bash
git tag -a release_125 "$BLUE_SHA" -m "Release v1.25"
git push origin refs/tags/release_125
gh release create release_125 --repo Azure/enterprise-scale-aifactory \
  --verify-tag --target release/v1.25 --title "Release v1.25" \
  --notes-file bootstrap/release-notes.txt --latest=false
```

No draft/prerelease flags are used; latest designation and default branch are not
changed. Branch-only publication does not authorize these additional operations.
Repository validation is not Azure deployment validation.
