# Enterprise Scale Azure Factory (ESAF) - BLUE consumer

[![Deploy to Azure](https://aka.ms/deploytoazurebutton)](https://portal.azure.com/#blade/Microsoft_Azure_CreateUIDef/CustomDeploymentBlade/uri/https%3A%2F%2Fraw.githubusercontent.com%2Fjostrm%2Fazure-enterprise-scale-ml%2Fportal-125%2Fportal%2Fazuredeploy.json/uiFormDefinitionUri/https%3A%2F%2Fraw.githubusercontent.com%2Fjostrm%2Fazure-enterprise-scale-ml%2Fportal-125%2Fportal%2Fform.json)
> [!NOTE]
> **Deploy to Azure is a quick test using PURPLE's portal template.** For a governed factory, start with BLUE's [consumer setup](documentation/bootstrapping.md) and use PURPLE's app, CLI or Factory API.

[Full setup & usage guide](https://github.com/jostrm/azure-enterprise-scale-ml/blob/release/v1.25/documentation/v2/20-29/24-end-2-end-setup.md) |
[Full variable documentation](https://jostrm.github.io/azure-enterprise-scale-ml/)

BLUE is your consumer starting point for the Enterprise Scale Azure Factory. Keep your configuration here and reuse [PURPLE's shared accelerator](https://github.com/jostrm/azure-enterprise-scale-ml) through a versioned Git submodule.

![Enterprise Scale Azure Factory header](https://raw.githubusercontent.com/jostrm/azure-enterprise-scale-ml/main/documentation/v2/10-19/images/header.png)
Explore the [Architecture library](https://jostrm.github.io/azure-enterprise-scale-ml/architectures/) for the three deployment designs.
![Private AI Factory landing zones and isolated project teams](https://raw.githubusercontent.com/jostrm/azure-enterprise-scale-ml/main/documentation/v2/10-19/images/14-eslz-full-1.png)

## Per environment (Dev, Stage, Prod) - zoomed in
<p align="center">
<a href="https://jostrm.github.io/azure-enterprise-scale-ml/architectures/"><img src="https://raw.githubusercontent.com/jostrm/azure-enterprise-scale-ml/main/documentation/v2/20-29/images/esaf-architecture-external-hub.png" width="100%" alt="ESAF with an external hub: common and project resources connected to your hub, Microsoft 365, Power Platform, SharePoint and Fabric."></a><br>
<sub><b>ESAF with an external hub.</b> Explore the numbered code templates and the alternative <b>Standalone - Own Hub</b> and <b>Standalone</b> designs in the Architecture library.</sub>
</p>

<p align="center">
<b>Private, WAF-aligned full-stack landing zones with AI on Azure, built on an accelerator used since 2019.</b><br>
Bring governed Microsoft Foundry, Azure Machine Learning and full-stack application services into isolated <b>Dev, Stage and Prod</b> environments.<br>
PURPLE's current catalog covers <b>54+ Azure resources</b> and <b>147 reusable use-case templates</b> through Agent Factory and ML Factory, designed for the factory's automated landing zones.<br>
Explore the <a href="https://jostrm.github.io/azure-enterprise-scale-ml/resources/"><b>Resources Library</b></a> and <a href="https://jostrm.github.io/azure-enterprise-scale-ml/code-templates/"><b>Code Template Library</b></a>.<br>
<b>Plug-and-play templates, with a project way of working.</b> BLUE keeps your repository and configuration separate from the shared implementation.
</p>

<table>
<tr>
<td width="50%" rowspan="2" valign="top">
<div align="center"><a href="https://github.com/jostrm/azure-enterprise-scale-ml/blob/main/documentation/v2/10-19/10-factory-onion-architecture-v2.md"><img src="https://raw.githubusercontent.com/jostrm/azure-enterprise-scale-ml/main/documentation/v2/10-19/images/10-factory-onion-architecture-v2.gif" width="72%" alt="AI Factory onion architecture: five deployment layers and the time spent in each layer."></a></div>
<sub><b>Architecture</b> - Choose your entry point: Azure portal, Factory API, SDK, pipelines or Bicep.</sub><br><br>
<a href="https://github.com/jostrm/azure-enterprise-scale-ml/blob/main/documentation/v2/10-19/11-architecture-diagrams.md"><img src="https://raw.githubusercontent.com/jostrm/azure-enterprise-scale-ml/main/documentation/v2/10-19/images/10-two-architectures-v2-small.png" width="100%" alt="AI Factory project architectures: a private floor for each team."></a><br>
<sub><b>Project architectures</b> - Give each team a private floor and select the services its projects need.</sub>
</td>
<td width="50%" valign="top">
<a href="https://github.com/jostrm/azure-enterprise-scale-ml/blob/main/documentation/v2/30-39/37-mlops.md"><img src="https://raw.githubusercontent.com/jostrm/azure-enterprise-scale-ml/main/documentation/v2/10-19/images/concepts/mlops.gif" width="100%" alt="MLOps: versioned data, training, evaluation, registration, approved release and monitoring."></a><br>
<sub><b>MLOps</b> - Take versioned data through training and approved releases to a monitored model.</sub>
</td>
</tr>
<tr>
<td width="50%" valign="top">
<a href="https://github.com/jostrm/azure-enterprise-scale-ml/blob/main/usecase_code/40-agent-factory/readme.md"><img src="https://raw.githubusercontent.com/jostrm/azure-enterprise-scale-ml/main/documentation/v2/10-19/images/concepts/dataops-rag.gif" width="100%" alt="GenAIOps: DataOps and retrieval-augmented generation with permitted, cited evidence."></a><br>
<sub><b>GenAIOps</b> - Connect governed knowledge to grounded answers.</sub>
</td>
</tr>
</table>

- **One governed lifecycle.** Use PURPLE's reviewed Factory API through the CLI, Python SDK, wizards or Azure Function to create, update and delete factories, scale sets and projects.
- **Private by design.** Reuse hub-spoke or Virtual WAN networking, private endpoints, DNS and team isolation, with Bicep orchestrated by GitHub Actions or Azure DevOps.
- **Operating models included.** Build on DataOps, MLOps and GenAIOps templates designed for the secure infrastructure. Explore the [147 use-case templates](https://github.com/jostrm/azure-enterprise-scale-ml/blob/main/usecase_code/readme.md).
- **Subscription vending.** Use PURPLE's automated subscription setup for a subscription/landing zone per team, or share a scale set across teams for sandbox and hackathon scenarios.

<p align="center">
<a href="documentation/bootstrapping.md"><b>Set up BLUE</b></a> &nbsp;|&nbsp;
<a href="https://github.com/jostrm/azure-enterprise-scale-ml/blob/main/documentation/v2/10-19/10-factory-onion-architecture-v2.md"><b>Architecture</b></a> &nbsp;|&nbsp;
<a href="https://github.com/jostrm/azure-enterprise-scale-ml/blob/main/documentation/v2/10-19/22-lifecycle-azure-function.md"><b>Lifecycle API</b></a> &nbsp;|&nbsp;
<a href="https://github.com/jostrm/azure-enterprise-scale-ml/blob/89eca66185366a702b026cec8c938570548c649c/usecase_code/40-agent-factory/readme.md"><b>Agent Factory</b></a> &nbsp;|&nbsp;
<a href="https://github.com/jostrm/azure-enterprise-scale-ml/blob/89eca66185366a702b026cec8c938570548c649c/usecase_code/50-ml-model-factory/readme.md"><b>ML Factory</b></a> &nbsp;|&nbsp;
<a href="https://github.com/jostrm/azure-enterprise-scale-ml/blob/main/documentation/v2/README.md"><b>Documentation</b></a><br>
<sub>Shared capabilities and artwork come from PURPLE; your consumer repository starts here in BLUE.</sub>
</p>

The overview and illustrations follow PURPLE's current catalog; the [compatibility matrix](documentation/bootstrapping.md#compatibility-matrix) describes BLUE's selected release. Newer artwork or catalog entries do not change the pinned implementation.

---

# Welcome to BLUE

BLUE bootstraps your consumer repository; PURPLE supplies the versioned shared implementation through a Git submodule.

Keep your configuration and orchestration entry points here. Reuse PURPLE's infrastructure, lifecycle tooling, Agent Factory and ML Factory without copying or forking the shared implementation.

**v1.25 and newer only:** consumer configuration lives in `azurefactory/register.json`. BLUE does not initialize or run the legacy `aifactory/` layout. Both folders are not needed.

[Full setup & usage guide](https://github.com/jostrm/azure-enterprise-scale-ml/blob/release/v1.25/documentation/v2/20-29/24-end-2-end-setup.md) |
[Full variable documentation](https://jostrm.github.io/azure-enterprise-scale-ml/)

## Quickstart - v1.25

Requires Git, Bash (Git Bash on Windows) and Python 3.10+. GitHub setup also requires an authenticated GitHub CLI with destination-repository permissions and organization SSO approval where applicable.

```bash
git -c core.longpaths=true clone --branch release/v1.25 --recurse-submodules \
  https://github.com/Azure/enterprise-scale-aifactory.git my-aifactory
cd my-aifactory
bash 01b-BYORepo-init-template-files-once.sh --dry-run
bash 01b-BYORepo-init-template-files-once.sh
```

This initializes the empty registered catalog and PURPLE's CLI/helper bundle, not Azure resources. Factory configuration requires a compatible Factory API; deployment is separately reviewed. Choose your repository ownership route:

| Route | Start here |
|---|---|
| GitHub full mirror to a confirmed new/empty repository | [Mirror bootstrap and `.env` setup](documentation/bootstrapping.md#a-github-mirror) |
| GitHub **Use this template** | [Include all branches, then select v1.25](documentation/bootstrapping.md#b-github-use-this-template) |
| Empty Azure DevOps / bring your own repository | [Copy-ready setup and pipeline configuration](documentation/bootstrapping.md#c-empty-azure-devops-or-bring-your-own-repository) |

The v1.25 gitlink pins PURPLE commit `89eca66185366a702b026cec8c938570548c649c`. Recursive clones reproduce that commit; branch metadata is only for explicit future updates.

See [configuration, compatibility and safe upgrades](documentation/bootstrapping.md). Optional services stay opt-in. Disabling a feature flag does **not** necessarily delete existing resources or stop ongoing costs; review the resource lifecycle, retained data and billing before making changes.

## Available through PURPLE

[Full setup & usage guide](https://github.com/jostrm/azure-enterprise-scale-ml/blob/release/v1.25/documentation/v2/20-29/24-end-2-end-setup.md) |
[Full variable documentation](https://jostrm.github.io/azure-enterprise-scale-ml/) |
[Agent Factory](https://github.com/jostrm/azure-enterprise-scale-ml/blob/89eca66185366a702b026cec8c938570548c649c/usecase_code/40-agent-factory/readme.md) |
[ML Factory](https://github.com/jostrm/azure-enterprise-scale-ml/blob/89eca66185366a702b026cec8c938570548c649c/usecase_code/50-ml-model-factory/readme.md)

BLUE implements repository bootstrap, not the shared services themselves. No Azure deployment is performed by repository setup.

[License](LICENSE) | [Contributing and CLA](CONTRIBUTING.md) | [Code of conduct](CODE_OF_CONDUCT.md) | [Security](SECURITY.md) | [Support](SUPPORT.md) | [Microsoft trademark guidelines](https://www.microsoft.com/en-us/legal/intellectualproperty/trademarks/usage/general)

Microsoft trademarks must not imply sponsorship of modified versions; third-party marks remain subject to their owners' policies.
