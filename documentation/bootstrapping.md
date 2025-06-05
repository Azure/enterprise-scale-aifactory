# Bootstrapping a new AIFactory and an AI Project

## Prerequisites

* [Azure CLI (az)](https://aka.ms/install-az) - to manage Azure resources
* [GitHub CLI (gh) version >=2.64.0](https://cli.github.com/) - to create GitHub repo and create environment variables and secrets
    - Install: Git for Windows (Git Bash terminal in VS Cide) with CLI 2.64.0 https://git-scm.com/downloads/win

### Nice to have (Prerequisites if you want to DEBUG)
* [BICEP (.bicep)](https://learn.microsoft.com/en-us/azure/azure-resource-manager/bicep/install) - to create (IaC) Azure resources
* [Powershell (.ps1)](https://aka.ms/install-powershell) - to orchestrate creation (IaC) of Azure resources

### You will also need:
* [Azure Subscription](https://azure.microsoft.com/free/) - sign up for a free account.
* Microsoft EntraID: Permissions to create a Service Principal (SP) in your Microsoft Entra ID (f.k.a. Azure AD Tenant)
* Permissions to assign the Owner role to the SP within the subscription.
* [GitHub Account](https://github.com/signup) - sign up for a free account.

## BOOTSTRAP - Common for A and B

1. **Create a Service Principal**

   We need a Service Principla with OWNER permission on the Dev, Stage, Permissions, to be able to create all Azure services, and set RBA roles to services and users, via the GHA workflows. <br>
   Create a service principal using the following command:

   ```sh
   az ad sp create-for-rbac --name "<your-service-principal-name>" --role Owner --scopes /subscriptions/<your-subscription-id> --sdk-auth
   ```

   > Ensure that the output information (Application ID,Object Id, Secret) created, is properly saved for future use. 
   >
   > Recommendation: Store it in a Azure Keyvault as secrets.
     ```sh
        aifactory-common-sp-id="qwerty-asdf-asd1123dfsdf-asdf123ds" // clientId or appId
        aifactory-common-sp-oid="asdf-asdf-asd1123dfsdf-asdf123ds" // ObjectId of service principal (not application itself)
        aifactory-common-sp-secret="afsdASDF!@asdf123"
        tenant-id="123as-df1231q-dsadar-123qe133"
     ```

2. **Update environment variables (.env) and sync them to your Github Variables**

    In your root directory.
   Create a copy of the `.env.template` file with this filename `.env`

    ```sh
    cp .env.template .env
    ```

    Open the `.env` with a text editor and update the variables:

    Here is an example of the `.env` file (note that you can use the same subscription for all environments)

   ```python
   # Once: Github info
    GITHUB_USERNAME="<todo>"
    GITHUB_USE_SSH="false"
    GITHUB_TEMPLATE_REPO="azure/enterprise-scale-aifactory"
    GITHUB_NEW_REPO="<todo>/enterprise-scale-aifactory-usage-1" # "<your_github_user_or_organization_id>/<new-repo-name>"
    GITHUB_NEW_REPO_VISIBILITY="public" # public, private, internal
    TENANT_ID="<todo>" # Once: Tenant info  (Configure once)
    TENANT_AZUREML_OID="<todo>" # Azure Machine Learning service principle Object ID. In Entra ID: "Azure Machine Learning" with AppId such as:0736f41a-0425-4b46-bdb5-1563eff02385

    # Once: AI Factory - Globals (Configure once)
    AIFACTORY_LOCATION="swedencentral"
    AIFACTORY_LOCATION_SHORT="sdc"
    AISEARCH_SEMANTIC_TIER="disabled" # "free", "standard", "disabled"
    AIFACTORY_PREFIX="<todo>" # Max 6 characters. <company>-<aifactoryname> Examples: ["acme-ai-","acme-"" "mrvel-1-", "contoso-", "ms-ai-"]
    AIFACTORY_SUFFIX="-001" # <-XXX> If you have mutliple AIFactory's in different regions: Examples: ["-001", "-002", "-003"]
    LAKE_PREFIX="xxxyyy" # Max 8 chars. Datalake storage account in AI Factory common. Example: xxxyyy
    USE_COMMON_ACR_FOR_PROJECTS="true" # Save cost. Share Azure Container Registry for Azure AI Foundry and Azure Machine Learning. "false", each project have its own ACR (more expensive)
    AIFACTORY_COMMON_ONLY_DEV_ENVIRONMENT="true" # true only Common-Dev will be created. false - it will create Dev, Stage, Prod environments in Azure
    AIFACTORY_SEEDING_KEYVAULT_SUBSCRIPTION_ID="<todo_id>" # [GH-Secret] Can be same as DEV_SUBSCRIPTION_ID
    AIFACTORY_SEEDING_KEYVAULT_NAME="<todo>" # [GH-Variable] Keyvault to store secrets with names mapped to PROJECT_SERVICE_PRINCIPAL_KV_S_NAME_APPID,...
    AIFACTORY_SEEDING_KEYVAULT_RG="<todo>" # Resource Group name for Send Keyvault
    COMMON_SERVICE_PRINCIPAL_KV_S_NAME_APPID="esml-common-bicep-sp-id" # Seeding Keyvault secret name for common SP AppId. Used for all environments
    COMMON_SERVICE_PRINCIPAL_KV_S_NAME_SECRET="esml-common-bicep-sp-secret" # Seeding Keyvault secret name (not the secret itself, only the name in keyvault)
    KEYVAULT_SOFT_DELETE="7" # 90 days is default. 0 is disabled. 90 days is recommended.
    USE_AD_GROUPS="false" # true, use AD groups for project members & advanced Personas. false, use individual ObjectID's and simple mode Personas

    # Once / per scale set: AI Factory - Environments: Dev, Stage, Prod (Configure once, or per AI Factory scale set)
    DEV_SUBSCRIPTION_ID="<todo_id>" # [GH-Secret]
    STAGE_SUBSCRIPTION_ID="<todo_id>" # [GH-Secret]
    PROD_SUBSCRIPTION_ID="<todo_id>" # [GH-Secret]
    DEV_CIDR_RANGE="20" # DEV_CIDR_RANGE will replace XX in the template: 10.XX.0.0/16
    STAGE_CIDR_RANGE="30" # 10.XX.0.0/16
    PROD_CIDR_RANGE="40" # 10.XX.0.0/16

    # Sometimes: UPDATE AIFactory: If you want to upgrade the AIFactory. E.g. if you go from submodule 'release/v1.20' to 'release/v1.21' your AIFactory will be upgraded to 1.21 (add new private dns zones, etc)
    AIFACTORY_VERSION_MAJOR="1"
    AIFACTORY_VERSION_MINOR="20" # 2025-05-23: 120_LTS = release/v.1.20

    # PRE PROJECT ############################# PRE SETUP of a PROJECT - UPDATE THIS
    PROJECT_NUMBER="001" # unique number per project within an AI Factory Example: "001", "002", "003"
    PROJECT_MEMBERS="<todo_object_id>,<todo_object_id>" #[GH-Secret] ObjectID or users (OR AD groups , if USE_AD_GROUPS=true) in a commas separated list, without space
    PROJECT_MEMBERS_EMAILS="<todo_email>, <todo_email>" # Email adresses, names, or some sort id ID, in a commas separated list, mapping to above ObjectID list
    PROJECT_MEMBERS_IP_ADDRESS="<todo_ip>,<todo_ip_range>" # [GH-Secret] IP (IPv4) adresses in a commas separated list, without space, to whitelist to acccess UI in Azure. 124.56.78.0/24 is an example of a range
    ### PRE PROJECT END ############################# E

    # POST ############################# POST SETUP of a PROJECT - UPDATE THIS
    RUN_JOB1_NETWORKING="true" # true, when creating a new project. set to false if you want to add services to a project. 
    # aifactory_salt_random: Needed for updating an AIFACTORY project (add service etc)
    AIFACTORY_SALT_RANDOM="<10>" # 10 characters. Look at the "User created Mnaged Identity". It is a unique random value. This '19-2858-4a' in that: 'mi-aca-prj001-sdc-dev-abcde19-2858-4a-001'
    # aifactory_salt: Needed to setup DATALAKE for ESML projects
    AIFACTORY_SALT="<5>" # 5 characters. This 'abcde' in that: 'mi-aca-prj001-sdc-dev-abcde19-2858-4a-001' A deteministic unique value
    # POST SETUP - END

    ################################ OPTIONAL - START ################################

    # OPTIONAL - Only change if you have different secret names in seeding keyvault (See PREREQUISITES in documentation)
    PROJECT_SERVICE_PRINCIPAL_KV_S_NAME_APPID="esml-project001-sp-id" # Seeding Keyvault secret name for project specific SP AppId. Not the IaC SP
    PROJECT_SERVICE_PRINCIPAL_KV_S_NAME_OID="esml-project001-sp-oid"  # Seeding Keyvault secret name for project specific SP ObjecId. Not the IaC SP
    PROJECT_SERVICE_PRINCIPAL_KV_S_NAME_S="esml-project001-sp-secret" #[GH-Secret] Seedig Keyvault secret name for project specific SP secret. Not the IaC SP
    PROJECT_TYPE="genai-1" # What default project type to deploy? [esml,genai-1,genai-2]

    # OPTIONAL - Bring your own subnets (BYO_subnets=true) - optional (leave empty string to disable).  Otherwise, leave it empty and the pipeline will create new subnets, based on the CIDR in 12-esml-cmn-parameters.json
    BYO_SUBNETS="false" # false, the default subnets created by the pipeline. Github Actions workflow will automatically not run Networking step, if true
    DEV_NETWORK_ENV="dev-" # initial custom prefix: "dev-" Default is empty string. Set to empty if  BYO_subnets: "false"
    STAGE_NETWORK_ENV="stage-" # Example: "test-"
    PROD_NETWORK_ENV="prod-" # # Example: "prd-"
   ```

3. **Authenticate with Azure and GitHub**
You need to login via `Azure CLI` and `Github CLI`, but recommendation is to also test login via `Powershell`. 
    - NB! Recommendation is to use a service principal when logging in. Not your user id.
    - The Service Principal should have OWNER permission to all 3 subscriptions (Dev, Test, Prod)
    - Test the login for all 3 subscriptions using `az cli` and `powershell` as below: 

   a) Log in to Azure CLI with your user ID, to a specific tenant

   ```sh
   az login --tenant $tenantId
   ```

   b) Log in to Azure CLI with a service principal, to a specific tenant

   ```sh
    # Define the variables
    clientId="your-client-id"
    clientSecret="your-client-secret"
    tenantId="your-tenant-id"
    subscriptionId="your-subscription-id"
    
    az login --service-principal -u $clientId -p $clientSecret --tenant $tenantId
    az account set --subscription $subscriptionId
   ```

   c) Log in to GitHub CLI:

   ```sh
    gh auth login
   ```

## BOOTSTRAP Option A) Bring-Your-Own-Repo

[Documenation: ](https://github.com/jostrm/azure-enterprise-scale-ml/blob/main/environment_setup/aifactory/bicep/copy_to_local_settings/github-actions/readme.md)
### **Run `01b-BYORepo-init-template-files-once.sh`**

This will add the submodule to your repo. 
This will copy templates and files from the *Enterprise Scale AIFactory* submodule.
At the end of its execution, the script will have created and initialized files and templates under a root folder called `aifactory` locally in your repo. You will end up with 2 folders in the repository with new files:
- **submodule**: will appear as a folder called `azure-enterprise-scale-ml` in your Github repo at root
- **templates**: will appear as a folder called `aifactory` in your Github repo at root

- **Filepath (root):** [../01b-BYORepo-init-template-files-once.sh](../01b-BYORepo-init-template-files-once.sh)  (Change directory to root, and run the bash as below)
    ```sh
    ./01b-BYORepo-init-template-files-once.sh
    ```

### **Run `02b-GH-create-or-update-github-variables.sh`**

This will create Github Variables and Secrets in Github based on your .env file <br>
The logic is "create if not exists", e.g. if you have a variable it will update that. The service principle credentials will not be updated, this you need to do manually, see step 4. 
- Change directory to root, and run the bash as:
```sh
./02b-GH-create-or-update-github-variables.sh
```

### A3. **Run `03b-GH-add-aifactory-pipelines-once.sh`** 

This will copy the templates from the `aifactory` folder, for Github Actions into your repo's .github/workflows/github-actions
Note that it will first delete the folder .github/workflows if exists.
    - Change directory to root, and run the bash as:
       ```sh
        ./03b-GH-add-aifactory-pipelines-once.sh
        ```

### A4. **Verify/Edit the GitHub Environment Variables/Secrets**
Go to the Github repository and validate the following GitHub environment variables for three environments: `DEV`, `STAGE`, and `PRODUCTION`. <br>
If they do not match your .env file, just redo step 2 e.g. run `02b-GH-create-or-update-github-variables.sh`. E.g. the variables looks similar to as below: <br>

> [!IMPORTANT]
> You need to manually set the `AZURE_CREDENTIALS` including secret for three environments: `DEV`, `STAGE`, and `PRODUCTION`. Note: 
>

   The `AZURE_CREDENTIALS` secret should be formatted as follows:
    
   ```json
   {
       "clientId": "your-client-id-aka-appId",
       "clientSecret": "your-client-secret-aka-servicPrincipalSecret",
       "subscriptionId": "your-subscription-id",
       "tenantId": "your-tenant-id"
   }
   ```

   > **Note:** If you are only interested in experimenting with this accelerator, you can use the same subscription, varying only `AZURE_ENV_NAME` for each environment, and use the same service principal for all three environments.<br>
   > - In production we recommend to have three different service principals, one per environment. And set the OWNER permissions on the respective service principal to each Azure subscription.

### A5. **Run GitHub Actions**

> [!NOTE]
> Ensure that GitHub Actions are enabled in your repository, as in some cases, organizational policies may not have this feature enabled by default. To do 
> this, simply click the button indicated in the figure below. 
   
Either run them manually from Github, or you may use the boostrap file: [04ab-setup-infra-aifactory.sh](../04ab-setup-infra-aifactory.sh)
    
**The bootstrap file will:**
- 1) Ensure Github variables are UPDATED from env file
- 2) Ensure baseline PARAMETERS files are UPDATED from env file (since they are used in the powershell GenDynNetwork, SubCalc, etc)
    - TODO: Do this manually for now.Automation is currently turned off.
- 3) Ensure Azure providers are enabled (create if not exists logic)
- 4) Ensure Private DNS zones exists(create if not exists logic) - in "hub", if flag is set to true, otherwise in AI Factory common resource group (Standalone mode, which is default)
- 5) Ensure Azure policies are created on Subscription level for enforcing extra security and resiliency.
- 6) Run Github pipelines (infra-aifactory-common -> infra-project-genai) Change to PROJECT_TYPE=`esml` in .env instead of default `esgenai-1`.

Afterwards it will have executed a Github Action workflow, that sets up Azure infrastructure, for only the DEV environment in this case.
- It will also setup the first project of type `esgenai-1` containing Azure services for RAG such as Azure OpenAI, Azure AI Foundry, Azure AI Search.
- It will also create all networking, private endpoints, role-based-access control for the services to be able to talk to each other, and for the `PROJECT_MEMBERS` to be able to access the Azure services.
  
   **For Bash:**

   ```sh
   ./04ab-setup-infra-aifactory.sh
   ```
    > **Note:** If you also want to setup the infrastructure for STAGE and PROD environemnt, simply edit the variable in the script called `dev_stage_prod=dev` to `stage` or `prod` and re-run the script.

## BOOTSTRAP Option B) Mirror-repo

- B1)  **Bootstrap (mirror-repo) - Run the Scripts**
Make sure you have done the common part, e.g. [BOOTSTRAP - Common for A and B](#bootstrap---common-for-a-and-b) and edited the env. file. Run [01a-GH-mirror-repo-from-template-once.sh](../01a-GH-mirror-repo-from-template-once.sh)
  
   **For Bash:**

   ```sh
   ./01a-GH-mirror-repo-from-template-once.sh
   ```

    This bootstrap script will create a mirror-repo, your own repo, and open VS Code to the local representation, and provide a link to your Github repo
    At the end of its execution, the script will have created Azure resources and 1 AIFactory project, of type ESGenAI (which is the default type)

- B2) **Do steps A2,A3,A4,A5** mentioned in previous section [BOOTSTRAP Option A) Bring-Your-Own-Repo](#bootstrap-option-a-bring-your-own-repo)

DONE!

# MORE INFO: Add or Refresh Submodule

**Add - with long path**

```sh
git config --system core.longpaths true
```

**Add**

```sh
git submodule add https://github.com/jostrm/azure-enterprise-scale-ml
```

**Refresh**

```sh
git submodule update --init --recursive
git submodule foreach 'git checkout main || git checkout -b main origin/main'
```
