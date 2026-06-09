#!/bin/bash

# ANSI color codes
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Load .env file
if [ -f .env ]; then
  set -o allexport
  source .env
  set -o allexport -
else
  echo "Error: .env file not found."
  exit 1
fi

# 01. Setup and Preparation
echo -e "${YELLOW}01. Copy environment variables locally to Github environments${NC}"
# Read the variables from the .env file
set -a # Enable export of all variables
source .env # Source the .env file
set +a # Disable export of all variables

if [ -f ".env" ]; then
    if [ -z "$GITHUB_USERNAME" ]; then
        echo -e "${RED}Failed to read the first variable,GITHUB_USERNAME, from .env.${NC}"
        exit 1
    else
        echo -e "${GREEN}Successfully read the first variable GITHUB_USERNAME=${GITHUB_USERNAME}, from .env file${NC}"
    fi
else
    echo -e "${RED}.env file does not exist.${NC}"
    exit 1
fi

# Define the temporary directory within the current directory
current_dir=$(pwd)

#temp_dir="$current_dir/temp"
temp_dir="../temp"

# Create the temporary directory
rm -rf "$temp_dir"
mkdir -p "$temp_dir"

# Ensure the temporary directory is removed on script exit
trap "rm -rf $temp_dir" EXIT

# Change to the temporary directory
cd "$temp_dir"

# Setup additional variables
if [ "$GITHUB_USE_SSH" = "true" ]; then
    github_template_repo_uri="git@github.com:${GITHUB_TEMPLATE_REPO}.git"
else
    github_template_repo_uri="https://github.com/${GITHUB_TEMPLATE_REPO}.git"
fi
if [ "$GITHUB_USE_SSH" = "true" ]; then
    github_new_repo_uri="git@github.com:${GITHUB_NEW_REPO}.git"
else
    github_new_repo_uri="https://github.com/${GITHUB_NEW_REPO}.git"
fi
github_new_repo_name=${GITHUB_NEW_REPO##*/}
github_template_repo_name=${GITHUB_TEMPLATE_REPO##*/}
destination_dir="../$github_new_repo_name"

# Get the GitHub CLI version
gh_version=$(gh --version | grep -oP '\d+\.\d+\.\d+')
gh_version_once=$(gh --version | grep -oP '\d+\.\d+\.\d+' | head -n 1)

# Function to compare versions
version_lt() {
    [ "$1" != "$2" ] && [ "$(printf '%s\n' "$1" "$2" | sort -V | head -n1)" = "$1" ]
}

# Check if gh_version is below 2.64.0
if version_lt "$gh_version" "2.64.0"; then
    echo -e "${RED}Error: GitHub CLI version 2.64.0 or higher is required. Current version: $gh_version${NC}"
    echo -e "${YELLOW}Tip: If you have lower version than 2.14.1 you need to uninstall Git, and remove the folder manually on Windows: C:\Program Files\Git manually, and reinstall https://git-scm.com/downloads/win ${NC}"
    exit 1
fi

echo -e "${GREEN}Github CLI Version: ${gh_version_once} ${NC}"

echo -e "\e[33mBootstraping Parameters\e[0m"
echo -e "\e[36mGitHub Username:\e[0m $GITHUB_USERNAME"
echo -e "\e[36mGitHub Use SSH:\e[0m $GITHUB_USE_SSH"
echo -e "\e[36mGitHub Template Repo:\e[0m $GITHUB_TEMPLATE_REPO"
echo -e "\e[36mGitHub Template Repo name:\e[0m $github_template_repo_name"
echo -e "\e[36mGitHub Template Repo URI:\e[0m $github_template_repo_uri"
echo -e "\e[36mGitHub New Repo:\e[0m $GITHUB_NEW_REPO"
echo -e "\e[36mGitHub New Repo name:\e[0m $github_new_repo_name"
echo -e "\e[36mGitHub New Repo URI:\e[0m $github_new_repo_uri"
echo -e "\e[36mGitHub New Repo Visibility:\e[0m $GITHUB_NEW_REPO_VISIBILITY"
echo -e "\e[36mGitHub New Repo local path destination:\e[0m $destination_dir"

# Remove the existing local folder if it exists
if [ -d "$destination_dir" ]; then
    read -p "It seems like you already have initialized a repo, since local folder exsits at $destination_dir. Do you want to delete folder, and re-initalize(Y/n)? " choice
    if [[ "$choice" == "n" || "$choice" == "N" ]]; then
        echo "Exiting script."
        exit 1
    fi
    rm -rf "$destination_dir"
fi

# Check if the user is already logged in to GitHub
echo -e "${GREEN}Checking GitHub authentication status...${NC}"
gh auth status
if [ $? -ne 0 ]; then
    echo -e "${YELLOW}Not logged in to GitHub. Logging in...${NC}"
    gh auth login
    if [ $? -ne 0 ]; then
        echo -e "${RED}Failed to log in to GitHub.${NC}"
        exit 1
    else
        echo -e "${GREEN}Successfully logged in to GitHub.${NC}"
    fi
else
    echo -e "${GREEN}Already logged in to GitHub.${NC}"
fi

# Check if login was successful
if [ $? -ne 0 ]; then
    echo -e "${RED}Failed to log in to GitHub.${NC}"
    exit 1
else
    echo -e "${GREEN}Successfully logged in to GitHub.${NC}"
fi
# Prompt the user for confirmation
read -p "Continue (Y/n)? " choice
if [[ "$choice" == "n" || "$choice" == "N" ]]; then
    echo "Exiting script."
    exit 1
fi

# 02. Repository Creation and Initialization
echo -e "${YELLOW}02. New GitHub Repository Creation and Initialization.${NC}"

echo -e "$Current directory (for tempfiles): $(pwd) ${NC}"
echo -e "$Destination directory(for your repo locally): $destination_dir ${NC}"

# Check if the repository already exists
repo_exists=$(gh repo view "$GITHUB_NEW_REPO" > /dev/null 2>&1; echo $?)

if [ $repo_exists -ne 0 ]; then
    # Create a new GitHub repository
    echo -e "${YELLOW}Creating a new GitHub repository.${NC}"
    gh repo create "$GITHUB_NEW_REPO" --$GITHUB_NEW_REPO_VISIBILITY
    if [ $? -ne 0 ]; then
        echo -e "${RED}Failed to create new GitHub repository.${NC}"
        exit 1
    fi
else
    echo -e "${GREEN}New GitHub repository already exists.${NC}"
    git remote -v
fi

# Clone the template repository
echo -e "${YELLOW}Cloning template repository.${NC}"
git clone --bare "$github_template_repo_uri"
cd $github_template_repo_name.git

# Mirror-push to the new repository
git push --mirror "$github_new_repo_uri"

if [[ $? -ne 0 ]]; then
  if [[ "$GITHUB_USE_SSH" == "true" ]]; then
    echo "ERROR: Permission denied to GitHub repo. GITHUB_USE_SSH is true. Please look at this reference:"
    echo "https://docs.github.com/en/get-started/getting-started-with-git/about-remote-repositories#cloning-with-https-urls"
  else
    echo "ERROR: Permission denied to GitHub repo. GITHUB_USE_SSH is false, you are using HTTPS. Please look at this reference:"
    echo "https://docs.github.com/en/get-started/getting-started-with-git/about-remote-repositories#cloning-with-ssh-urls"    
  fi
  exit 1
fi

echo -e "${GREEN}Everything up-to-date${NC}"
cd ..
rm -rf $github_template_repo_name.git # rm -rf $template_project_repo_name.git

# ============================================================================
# Variable & Secret Bootstrap
# (kept in sync with 10-GH-create-or-update-github-variables.sh)
# - Repo-level variables: applied ONCE at repo scope to reduce per-env count
#   (GitHub limits the number of variables per environment).
# - Environment-level: only env-specific variables and secrets.
# This script is a ONE-TIME bootstrap, so it always targets all 3 environments
# (dev/stage/prod) and always seeds the AZURE_CREDENTIALS placeholder.
# ============================================================================

# Rate limit safety: pause to avoid GitHub secondary rate limits
op_counter=0
rate_limit_pause_after=50
rate_limit_pause_after_2=85
rate_limit_sleep_seconds=30

increment_counter() {
  op_counter=$((op_counter + 1))
  echo -e "${YELLOW}[${op_counter}] Processing: $1${NC}"
  if [[ $op_counter -eq $rate_limit_pause_after || $op_counter -eq $rate_limit_pause_after_2 ]]; then
    echo -e "${YELLOW}Hit ${op_counter} operations. Sleeping ${rate_limit_sleep_seconds}s to avoid GitHub secondary rate limits...${NC}"
    sleep "$rate_limit_sleep_seconds"
  fi
}

# Function to check if an env-level variable exists
check_variable_exists() {
  gh api repos/$GITHUB_NEW_REPO/environments/$1/variables/$2 > /dev/null 2>&1
}

# Function to create or update an env-level variable
create_or_update_variable() {
  local env=$1
  local name=$2
  local value=$3
  if [[ -z "$value" ]]; then
    echo -e "${YELLOW}Skipping variable '$name' for environment '$env' because the value is empty.${NC}"
    return
  fi
  increment_counter "variable $env/$name"
  if check_variable_exists $env $name; then
    gh api --method PATCH -H "Accept: application/vnd.github+json" repos/$GITHUB_NEW_REPO/environments/$env/variables/$name -f value="$value"
  else
    gh api --method POST -H "Accept: application/vnd.github+json" repos/$GITHUB_NEW_REPO/environments/$env/variables -f name=$name -f value="$value"
  fi
}

# Function to check if a secret exists
check_secret_exists() {
  gh secret list --repo $GITHUB_NEW_REPO --env $1 | grep -q $2
}

# Function to create or update a secret
create_or_update_secret() {
  local env=$1
  local name=$2
  local value=$3
  increment_counter "secret $env/$name"
  gh secret set $name --repo $GITHUB_NEW_REPO --env $env --body "$value"
}

# Repo-level variable helper
create_or_update_repo_variable() {
  local name=$1
  local value=$2
  if [[ -z "$value" ]]; then
    echo -e "${YELLOW}Skipping repo variable '$name' because the value is empty.${NC}"
    return
  fi
  echo -e "${YELLOW}[Repo] Setting variable: $name${NC}"
  gh variable set "$name" --repo "$GITHUB_NEW_REPO" --body "$value"
}

echo -e "${YELLOW}Bootstraps config from .env as Github repo/environment variables and secrets.${NC}"

# Get the GitHub CLI version
gh_version=$(gh --version | grep -oP '\d+\.\d+\.\d+' | head -n 1)

# Helper to get AZURE_ENV_NAME per environment
get_azure_env_name() {
  case "$1" in
    dev) echo "dev" ;;
    stage) echo "test" ;;
    prod) echo "prod" ;;
  esac
}

# All environments are bootstrapped on first-time setup
environments=("dev" "stage" "prod")

# ----------------------------------------------------------------------------
# Repo-scoped variables (replaces majority of per-env variables to stay
# under GitHub's per-environment variable limit). Mirrors repo_level_vars
# in 10-GH-create-or-update-github-variables.sh.
# ----------------------------------------------------------------------------
repo_level_vars=(
  # === Global AI Factory settings ===
  "AIFACTORY_LOCATION"
  "AIFACTORY_LOCATION_SHORT"
  "AIFACTORY_SUFFIX"
  "AIFACTORY_PREFIX"
  "TENANT_AZUREML_OID"
  "LAKE_PREFIX"
  "AISEARCH_SEMANTIC_TIER"

  # === RBAC model ===
  "USE_AD_GROUPS"
  "GROUPS_PROJECT_MEMBERS_ESML"
  "GROUPS_PROJECT_MEMBERS_GENAI_1"
  "GROUPS_CORETEAM_MEMBERS"
  "PERSONAS_PROJECT_ESML"
  "PERSONAS_PROJECT_GENAI_1"
  "PERSONAS_CORE_TEAM"

  # === Keyvault and security ===
  "KEYVAULT_SOFT_DELETE"
  "AIFACTORY_SEEDING_KEYVAULT_NAME"
  "AIFACTORY_SEEDING_KEYVAULT_RG"
  "COMMON_SERVICE_PRINCIPAL_KV_S_NAME_APPID"
  "COMMON_SERVICE_PRINCIPAL_KV_S_NAME_SECRET"
  "INPUT_COMMON_SPID_KEY"
  "INPUT_COMMON_SPSECRET_KEY"
  "INPUT_COMMON_SP_SECRET_KEY"
  "COMMON_SERVICE_PRINCIPLE_OID_KEY"

  # === Project settings ===
  "PROJECT_TYPE"
  "PROJECT_SERVICE_PRINCIPAL_KV_S_NAME_APPID"
  "PROJECT_SERVICE_PRINCIPAL_KV_S_NAME_OID"
  "PROJECT_SERVICE_PRINCIPAL_KV_S_NAME_S"
  "PROJECT_NUMBER"
  "PROJECT_MEMBERS_EMAILS"
  "PROJECT_IP_WHITELIST"
  "TAGS_PROJECT"

  # === Versioning ===
  "AIFACTORY_VERSION_MAJOR"
  "AIFACTORY_VERSION_MINOR"
  "AIFACTORY_SALT"
  "AIFACTORY_SALT_RANDOM"

  # === Networking ===
  "BYO_SUBNETS"
  "RUN_JOB1_NETWORKING"

  # === Cost optimization ===
  "USE_COMMON_ACR_FOR_PROJECTS"

  "ENABLE_DEFENDER_FOR_AI_SUB_LEVEL"
  "ENABLE_DEFENDER_FOR_AI_RESOURCE_LEVEL"
  "CMK"
  "CMK_KEY_NAME"
  "CMK_KEY_VERSION"
  "CMK_DISABLE_FOR_AI_SEARCH"
  "CMK_DISABLE_FOR_FOUNDRY"
  "ADMIN_AISEARCH_TIER"
  "PROJECT_PREFIX"
  "PROJECT_SUFFIX"
  "UPDATE_KEYVAULT_RBAC"
  "AIFACTORY_COMMON_ONLY_DEV_ENVIRONMENT"
  "ADMIN_USERNAME"
  "ADMIN_HYBRID_BENEFIT"
  "ADMIN_COMMON_RESOURCE_SUFFIX"
  "ADMIN_PRJ_RESOURCE_SUFFIX"
  "VNET_RESOURCE_GROUP_BASE"
  "VNET_NAME_BASE"
  "SUBNET_COMMON_BASE"
  "COMMON_VNET_CIDR"
  "COMMON_SUBNET_CIDR"
  "COMMON_SUBNET_SCORING_CIDR"
  "COMMON_PBI_SUBNET_NAME"
  "COMMON_PBI_SUBNET_CIDR"
  "COMMON_BASTION_SUBNET_NAME"
  "COMMON_BASTION_SUBNET_CIDR"
  "DISABLE_WHITELISTING_FOR_BUILD_AGENTS"
  "USE_COMMON_ACR_OVERRIDE"
  "ACR_IP_WHITELIST"
  "ACR_ADMIN_USER_ENABLED"
  "ACR_DEDICATED"
  "ACR_SKU"

  # === RBAC: Contributor role override ===
  "BYO_CONTRIBUTOR_ROLE_ID"
  "DISABLE_CONTRIBUTOR_ACCESS_FORUSERS"
  "DISABLE_RBAC_ADMIN_ON_RG_FORUSERS"
  "DISABLE_SUBNET_JOIN_ACTION"

  # === Complete mode vs Incremental mode ===
  "ENABLE_DELETE_FOR_DISABLED_RESOURCES"
  "DELETE_ALL_SERVICES_FOR_PROJECT"
  "DELETE_ALL_FOR_PROJECT"

  # === ENABLE_* flags ===
  "ENABLE_AI_SERVICES"
  "ENABLE_AI_FOUNDRY_HUB"
  "ENABLE_AI_FOUNDRY"
  "ENABLE_FOUNDRY_CAPHOST"
  "CLEAN_FOUNDRY_CAPHOST"
  "ENABLE_AIFACTORY_CREATED_DEFAULT_PROJECT_FOR_AIFV2"
  "ENABLE_DATAFACTORY"
  "ENABLE_DATAFACTORY_COMMON"
  "ENABLE_AZURE_MACHINE_LEARNING"
  "ENABLE_AKS_FOR_AZURE_ML"
  "ENABLE_AKS"
  "ENABLE_DATABRICKS"
  "ENABLE_AI_SEARCH"
  "ENABLE_AI_SEARCH_SHARED_PRIVATE_LINK"
  "ENABLE_AZURE_OPENAI"
  "ENABLE_AZURE_AI_VISION"
  "ENABLE_AZURE_SPEECH"
  "ENABLE_AI_DOC_INTELLIGENCE"
  "ENABLE_BING"
  "ENABLE_BING_CUSTOM_SEARCH"
  "ENABLE_CONTENT_SAFETY"
  "ENABLE_COSMOS_DB"
  "ENABLE_POSTGRESQL"
  "ENABLE_REDIS_CACHE"
  "ENABLE_SQL_DATABASE"
  "ENABLE_ELASTICSEARCH"
  "ENABLE_FUNCTION"
  "ENABLE_WEBAPP"
  "ENABLE_CONTAINER_APPS"
  "ENABLE_APPINSIGHTS_DASHBOARD"
  "ENABLE_LOGIC_APPS"
  "ENABLE_EVENT_HUBS"
  "ENABLE_BOT_SERVICE"

  # === Network env labels ===
  "DEV_NETWORK_ENV"
  "STAGE_NETWORK_ENV"
  "PROD_NETWORK_ENV"

  # === AKS networking ===
  "AKS_OUTBOUND_TYPE"
  "AKS_PRIVATE_DNS_ZONE"
  "AKS_AZURE_FIREWALL_PRIVATE_IP"

  # === Admin overrides ===
  "ADMIN_AKS_GPU_SKU_DEV_OVERRIDE"
  "ADMIN_AKS_GPU_SKU_TEST_PROD_OVERRIDE"
  "ADMIN_AKS_NODES_DEV_OVERRIDE"
  "ADMIN_AKS_NODES_TEST_PROD_OVERRIDE"
  "ADMIN_AKS_VERSION_OVERRIDE"
  "ADMIN_AML_CLUSTER_MAX_NODES_DEV_OVERRIDE"
  "ADMIN_AML_CLUSTER_MAX_NODES_TEST_PROD_OVERRIDE"
  "ADMIN_AML_CLUSTER_SKU_DEV_OVERRIDE"
  "ADMIN_AML_CLUSTER_SKU_TEST_PROD_OVERRIDE"
  "ADMIN_AML_COMPUTE_INSTANCE_DEV_SKU_OVERRIDE"
  "ADMIN_AML_COMPUTE_INSTANCE_TEST_PROD_SKU_OVERRIDE"
  "TAGS"
  "SERVICE_SETTING_DEPLOY_PROJECT_VM"
  "DEBUG_DISABLE_VALIDATION_TASKS"
  "ADMIN_AI_SEARCH_TIER"

  # === Service enable flags and BYO customization ===
  "UPDATE_AI_FOUNDRY"
  "FOUNDRY_DEPLOYMENT_TYPE"
  "DISABLE_AGENT_NETWORK_INJECTION"
  "VNET_RESOURCE_GROUP_PARAM"
  "VNET_NAME_FULL_PARAM"
  "SUBNET_COMMON"
  "SUBNET_COMMON_SCORING"
  "SUBNET_COMMON_POWERBI_GW"
  "SUBNET_PROJ_GENAI"
  "SUBNET_PROJ_AKS"
  "SUBNET_PROJ_AKS2"
  "SUBNET_PROJ_ACA"
  "SUBNET_PROJ_ACA2"
  "SUBNET_PROJ_DATABRICKS_PUBLIC"
  "SUBNET_PROJ_DATABRICKS_PRIVATE"
  "BYO_ASEV3"
  "BYO_ASE_FULL_RESOURCE_ID"
  "BYO_ASE_APP_SERVICE_PLAN_RESOURCE_ID"

  # === Model deployments ===
  "DEPLOY_MODEL_GPT_X"
  "MODEL_GPTX_NAME"
  "MODEL_GPTX_VERSION"
  "MODEL_GPTX_SKU"
  "MODEL_GPTX_CAPACITY"
  "DEPLOY_MODEL_TEXT_EMBEDDING_ADA_002"
  "DEPLOY_MODEL_TEXT_EMBEDDING_3_LARGE"
  "DEPLOY_MODEL_TEXT_EMBEDDING_3_SMALL"
  "DEFAULT_EMBEDDING_CAPACITY"
  "DEPLOY_MODEL_GPT_54_MINI"
  "DEFAULT_GPT_54_MINI_VERSION"
  "DEPLOY_MODEL_GPT_4O"
  "DEFAULT_GPT_4O_VERSION"
  "DEFAULT_GPT_CAPACITY"
  "DEFAULT_MODEL_SKU"

  # === Databases ===
  "COSMOS_KIND"
  "POSTGRES_ADMIN_EMAILS"
  "ELASTIC_TYPE"
  "ELASTIC_EMAIL"
  "ELASTIC_FIRST_NAME"
  "ELASTIC_LAST_NAME"
  "ELASTIC_COMPANY_NAME"
  "ELASTIC_DEPLOYMENT_SIZE"
  "ELASTIC_SKU"

  # === Runtimes ===
  "FUNCTION_RUNTIME"
  "FUNCTION_VERSION"
  "WEBAPP_RUNTIME"
  "WEBAPP_RUNTIME_VERSION"
  "ASE_SKU"
  "ASE_SKU_CODE"
  "ASE_SKU_WORKERS"
  "ACA_W_REGISTRY_IMAGE"

  # === Foundry & AKS ===
  "FOUNDRY_API_MANAGEMENT_RESOURCE_ID"
  "AKS_SKU_NAME"
  "AKS_SKU_TIER"
  "AKS_ENABLE_PRIVATE_CLUSTER"

  # === Debug disables ===
  "DEBUG_DISABLE_05_BUILD_ACR_IMAGE"
  "DEBUG_DISABLE_61_FOUNDATION"
  "DEBUG_DISABLE_62_CORE_INFRASTRUCTURE"
  "DEBUG_DISABLE_63_COGNITIVE_SERVICES"
  "DEBUG_DISABLE_64_DATABASES"
  "DEBUG_DISABLE_65_COMPUTE_SERVICES"
  "DEBUG_DISABLE_66_AI_PLATFORM"
  "DEBUG_DISABLE_67_ML_PLATFORM"
  "DEBUG_DISABLE_68_INTEGRATION"
  "DEBUG_DISABLE_69_AIFOUNDRY_2025"
  "DEBUG_DISABLE_100_RBAC_SECURITY"
  "DEBUG_DISABLE_10_AIFACTORY_DASHBOARDS"
  "ADD_AI_FOUNDRY_HUB"
  "ADD_AI_FOUNDRY"
  "ADD_AI_SEARCH"
  "ADD_AZURE_MACHINE_LEARNING"
  "POLICY_EXEMPTION_ASSIGNMENT_IDS"
  "POLICY_EXEMPTION_DEFINITION_REFERENCE_IDS"
)

# Apply repo-level variables once
echo -e "${GREEN}Applying repo-level variables...${NC}"
for var_name in "${repo_level_vars[@]}"; do
  var_value="${!var_name}"
  # Strip outer single quotes from TAGS and TAGS_PROJECT
  if [[ "$var_name" == "TAGS" || "$var_name" == "TAGS_PROJECT" ]]; then
    var_value="${var_value#\'}"
    var_value="${var_value%\'}"
  fi
  create_or_update_repo_variable "$var_name" "$var_value"
done

# Create environments and set AZURE_ENV_NAME
for env in "${environments[@]}"; do
  gh api --method PUT -H "Accept: application/vnd.github+json" repos/$GITHUB_NEW_REPO/environments/$env
  create_or_update_variable "$env" "AZURE_ENV_NAME" "$(get_azure_env_name "$env")"
done

# Environment-specific secrets (same value across envs)
for env in "${environments[@]}"; do
    echo -e "${YELLOW}Setting environment-specific secrets for: $env${NC}"
    create_or_update_secret $env "AIFACTORY_SEEDING_KEYVAULT_SUBSCRIPTION_ID" "$AIFACTORY_SEEDING_KEYVAULT_SUBSCRIPTION_ID"
    create_or_update_secret $env "TENANT_ID" "$TENANT_ID"
    create_or_update_secret $env "PROJECT_MEMBERS" "$PROJECT_MEMBERS"
    create_or_update_secret $env "PROJECT_MEMBERS_IP_ADDRESS" "$PROJECT_MEMBERS_IP_ADDRESS"
done

# DEV environment specifics
create_or_update_variable "dev" "AZURE_LOCATION" "$AIFACTORY_LOCATION"
create_or_update_variable "dev" "AZURE_SUBSCRIPTION_ID" "$DEV_SUBSCRIPTION_ID"
create_or_update_variable "dev" "CIDR_RANGE" "$DEV_CIDR_RANGE"
create_or_update_variable "dev" "DEV_CIDR_RANGE" "$DEV_CIDR_RANGE"
create_or_update_variable "dev" "AIFACTORY_CIDR_XX" "$DEV_CIDR_RANGE"
create_or_update_variable "dev" "DEV_NETWORK_ENV" "$DEV_NETWORK_ENV"
create_or_update_variable "dev" "NETWORK_ENV" "$DEV_NETWORK_ENV"
create_or_update_secret "dev" "AZURE_CREDENTIALS" "replace_with_dev_sp_credentials"

# STAGE environment specifics
create_or_update_variable "stage" "AZURE_LOCATION" "$AIFACTORY_LOCATION"
create_or_update_variable "stage" "AZURE_SUBSCRIPTION_ID" "$STAGE_SUBSCRIPTION_ID"
create_or_update_variable "stage" "CIDR_RANGE" "$STAGE_CIDR_RANGE"
create_or_update_variable "stage" "STAGE_CIDR_RANGE" "$STAGE_CIDR_RANGE"
create_or_update_variable "stage" "AIFACTORY_CIDR_XX" "$STAGE_CIDR_RANGE"
create_or_update_variable "stage" "STAGE_NETWORK_ENV" "$STAGE_NETWORK_ENV"
create_or_update_variable "stage" "NETWORK_ENV" "$STAGE_NETWORK_ENV"
create_or_update_secret "stage" "AZURE_CREDENTIALS" "replace_with_stage_sp_credentials"

# PROD environment specifics
create_or_update_variable "prod" "AZURE_LOCATION" "$AIFACTORY_LOCATION"
create_or_update_variable "prod" "AZURE_SUBSCRIPTION_ID" "$PROD_SUBSCRIPTION_ID"
create_or_update_variable "prod" "CIDR_RANGE" "$PROD_CIDR_RANGE"
create_or_update_variable "prod" "PROD_CIDR_RANGE" "$PROD_CIDR_RANGE"
create_or_update_variable "prod" "AIFACTORY_CIDR_XX" "$PROD_CIDR_RANGE"
create_or_update_variable "prod" "PROD_NETWORK_ENV" "$PROD_NETWORK_ENV"
create_or_update_variable "prod" "NETWORK_ENV" "$PROD_NETWORK_ENV"
create_or_update_secret "prod" "AZURE_CREDENTIALS" "replace_with_prod_sp_credentials"

# TODO Future: dev.env / stage.env / prod.env
# gh secret set -f prod.env --env prod

echo -e "${GREEN}New repository created successfully.${NC}"

echo -e "${GREEN}Access your new repo in: \nhttps://github.com/$GITHUB_NEW_REPO ${NC}"

# Clone the new repository
echo -e "${YELLOW}Cloning the new GitHub repository${NC}"
echo -e "${GREEN}Local path: $destination_dir ${NC}"

git clone "$github_new_repo_uri" "$destination_dir"

active_dir=$(pwd)

cd "$destination_dir"

# Init subodule
echo -e "${YELLOW}Running init script 11-init-template-files-once.sh in new repo, to refresh submodule. ${NC}"
git submodule update --init --recursive
git submodule foreach 'git checkout main || git checkout -b main origin/main'
# ./11-init-template-files-once.sh

# Clean GIT history
git checkout --orphan cleaned-history
git add -A
git commit -m "Initial commit with cleaned history"
git branch -D main
git branch -m main
git push -f origin main

# echo -e "${RED}Troubleshooting 004${NC}"

# Create dev branch "if not exists"
if ! git ls-remote --exit-code --heads origin dev; then
  # Create the develop branch if it does not exist
  echo -e "${YELLOW}Create the develop branch if it does not exist${NC}"
  git checkout -b dev
  git push origin dev
else
  echo "Branch 'dev' already exists."
fi

# Setting default branch to dev
echo -e "${YELLOW}Setting default branch in the new repository.${NC}"
gh repo edit $GITHUB_NEW_REPO --default-branch dev


# DEV branch protection rule
# gh api \
#   --method PUT \
#   -H "Accept: application/vnd.github+json" \
#   -H "X-GitHub-Api-Version: 2022-11-28" \
#   repos/$GITHUB_NEW_REPO/branches/dev/protection \
#   -F "required_status_checks[strict]=true" \
#   -F "required_status_checks[contexts][]=evaluate-flow" \
#   -F "enforce_admins=true" \
#   -F "required_pull_request_reviews[dismiss_stale_reviews]=false" \
#   -F "required_pull_request_reviews[require_code_owner_reviews]=false" \
#   -F "required_pull_request_reviews[required_approving_review_count]=0" \
#   -F "required_pull_request_reviews[require_last_push_approval]=false" \
#   -F "allow_force_pushes=true" \
#   -F "allow_deletions=true" \
#   -F "block_creations=true" \
#   -F "required_conversation_resolution=true" \
#   -F "lock_branch=false" \
#   -F "allow_fork_syncing=true" \
#   -F "restrictions=null"

# REP= DESCRIPTION: 

#gh api -X PATCH "repos/$GITHUB_USERNAME/$GITHUB_NEW_REPO" -f description="Your repository. Your Enteprise Scale AI Factory."
#gh repo edit https://github.com/jostrm/azure-enterprise-scale-ml-usage-2 --description "Your Enteprise Scale AI Factory.Your repository.Created from the Azure Enterprise Scale ML template."

# Open VS Code
cd "$active_dir"
echo -e "${YELLOW}Now trying to open an new VS Code window with your new repo at $destination_dir....${NC}"
code "$destination_dir"