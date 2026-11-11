# Enterprise Scale AI Factory - BLUE consumer v1.25

BLUE bootstraps your consumer repository; PURPLE supplies the versioned shared implementation through a Git submodule.

Keep your configuration and orchestration entry points here. Reuse PURPLE's infrastructure, lifecycle tooling, Agent Factory and ML Factory without copying or forking the shared implementation.

[![Private AI Factory landing zones and isolated project teams](https://raw.githubusercontent.com/jostrm/azure-enterprise-scale-ml/main/documentation/v2/10-19/images/14-eslz-full-1.png)](https://github.com/jostrm/azure-enterprise-scale-ml/blob/89eca66185366a702b026cec8c938570548c649c/documentation/v2/20-29/24-end-2-end-setup.md)

## Quickstart - v1.25

Requires Git, Bash (Git Bash on Windows) and Python 3.10+. GitHub setup also requires an authenticated GitHub CLI with destination-repository permissions and organization SSO approval where applicable.

```bash
git clone --branch release/v1.25 --recurse-submodules \
  https://github.com/Azure/enterprise-scale-aifactory.git my-aifactory
cd my-aifactory
bash 01b-BYORepo-init-template-files-once.sh --dry-run
bash 01b-BYORepo-init-template-files-once.sh
```

This initializes local consumer files, not Azure resources. Choose your ownership route before configuring or running deployment pipelines:

| Route | Start here |
|---|---|
| GitHub full mirror to a confirmed new/empty repository | [Mirror bootstrap and `.env` setup](documentation/bootstrapping.md#a-github-mirror) |
| GitHub **Use this template** | [Include all branches, then select v1.25](documentation/bootstrapping.md#b-github-use-this-template) |
| Empty Azure DevOps / bring your own repository | [Copy-ready setup and pipeline configuration](documentation/bootstrapping.md#c-empty-azure-devops-or-bring-your-own-repository) |

The v1.25 gitlink pins PURPLE commit `89eca66185366a702b026cec8c938570548c649c`. Recursive clones reproduce that commit; branch metadata is only for explicit future updates.

See [configuration, compatibility and safe upgrades](documentation/bootstrapping.md). Optional services stay opt-in. Disabling a feature flag does **not** necessarily delete existing resources or stop ongoing costs; review the resource lifecycle, retained data and billing before making changes.

## Available through PURPLE

[Architecture and setup](https://github.com/jostrm/azure-enterprise-scale-ml/blob/89eca66185366a702b026cec8c938570548c649c/documentation/v2/20-29/24-end-2-end-setup.md) |
[Agent Factory](https://github.com/jostrm/azure-enterprise-scale-ml/blob/89eca66185366a702b026cec8c938570548c649c/usecase_code/40-agent-factory/readme.md) |
[ML Factory](https://github.com/jostrm/azure-enterprise-scale-ml/blob/89eca66185366a702b026cec8c938570548c649c/usecase_code/50-ml-model-factory/readme.md)

[![Layered AI Factory architecture and orchestration choices](https://raw.githubusercontent.com/jostrm/azure-enterprise-scale-ml/main/documentation/v2/10-19/images/10-factory-onion-architecture-v2.gif)](https://github.com/jostrm/azure-enterprise-scale-ml/blob/89eca66185366a702b026cec8c938570548c649c/documentation/v2/20-29/24-end-2-end-setup.md)

[![MLOps flow from versioned data to a monitored model](https://raw.githubusercontent.com/jostrm/azure-enterprise-scale-ml/main/documentation/v2/10-19/images/concepts/mlops.gif)](https://github.com/jostrm/azure-enterprise-scale-ml/blob/89eca66185366a702b026cec8c938570548c649c/usecase_code/50-ml-model-factory/readme.md)

[![DataOps and retrieval-augmented generation flow](https://raw.githubusercontent.com/jostrm/azure-enterprise-scale-ml/main/documentation/v2/10-19/images/concepts/dataops-rag.gif)](https://github.com/jostrm/azure-enterprise-scale-ml/blob/89eca66185366a702b026cec8c938570548c649c/usecase_code/40-agent-factory/readme.md)

Illustrations are maintained upstream on `main`; the [compatibility matrix](documentation/bootstrapping.md#compatibility-matrix) describes the selected release, not every capability shown in newer artwork. BLUE implements repository bootstrap, not the shared services themselves. No Azure deployment is performed by repository setup.

[License](LICENSE) | [Contributing and CLA](CONTRIBUTING.md) | [Code of conduct](CODE_OF_CONDUCT.md) | [Security](SECURITY.md) | [Support](SUPPORT.md) | [Microsoft trademark guidelines](https://www.microsoft.com/en-us/legal/intellectualproperty/trademarks/usage/general)

Microsoft trademarks must not imply sponsorship of modified versions; third-party marks remain subject to their owners' policies.

[![Two AI Factory project architectures, with a private floor for each team](https://raw.githubusercontent.com/jostrm/azure-enterprise-scale-ml/main/documentation/v2/10-19/images/10-two-architectures-v2-small.png)](https://github.com/jostrm/azure-enterprise-scale-ml/blob/89eca66185366a702b026cec8c938570548c649c/documentation/v2/20-29/24-end-2-end-setup.md)

Figure: Each team in the AI Factory, have their own floor with 1-35 resources, optinally to get above architectures. Each team can own multiple floors. You may turn ON/OFF Azure resources to remove cost. Easy to turn on again.
