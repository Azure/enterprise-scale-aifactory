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

# DIRECTORIES
current_dir=$(pwd)

# 01 - Ensure Github variables are UPDATED from env file
./10-create-or-update-github-variables.sh

# 02 - Ensure baseline PARAMETERS files are UPDATED from env file (since they are used in the powershell GenDynNetwork, SubCalc, etc)
 
# 03 - Ensure Azure providers are enabled (create if not exists)
pwsh ./aifactory/esml-util/26-enable-resource-providers.ps1

# 04 - Ensure Private DNS zones exists in "hub", if flag is set to true

pwsh ./aifactory/esml-util/27-create-private-dns-zones.ps1 -spID TODO -tenantID TODO -subscriptionID TODO8d1 -resourceGroupName TODO -location 'swedencentral'

# 05 - Ensure policies are created on Subscription level

RESOURCE_GROUP="your_resource_group"
LOCATION="your_location"
PARAMETERS_FILE="./aifactory/esml-util/28-Initiatives.parameters.json"
az deployment group create \
  --resource-group $RESOURCE_GROUP \
  --template-file ./aifactory/esml-util/28-Initiatives.bicep \
  --parameters @$PARAMETERS_FILE

# 06- Run Github pipelines (infra-aifactory-common -> infra-project-genai)

# Define variables
GITHUB_TOKEN="your_personal_access_token"
REPO_OWNER=${GITHUB_USERNAME} # "your_github_username_or_org"
REPO_NAME=${GITHUB_USERNAME} # "your_repository_name"
WORKFLOW_ID_ESML="infra-project-esml.yml"
WORKFLOW_ID_GENAI="infra-project-genai.yml"
REF="main"  # or the branch you want to trigger the workflow on
DEFAULT_ENV="dev"

if [ ${PROJECT_TYPE} = 'genai-1' ]; then
    echo -e "${YELLOW} Deploying GENAI project type ${NC}"
    # Function to trigger workflow_dispatch
    trigger_workflow_dispatch() {
      curl -X POST \
        -H "Accept: application/vnd.github.v3+json" \
        -H "Authorization: token ${GITHUB_TOKEN}" \
        https://api.github.com/repos/${REPO_OWNER}/${REPO_NAME}/actions/workflows/${WORKFLOW_ID_GENAI}/dispatches \
        -d "{\"ref\":\"${REF}\",\"inputs\":{\"default\":\"${DEFAULT_ENV}\"}}"
    }

elif [ ${PROJECT_TYPE} = 'esml' ]; then
    echo -e "${YELLOW} Deploying ESML project type ${NC}"
    # Function to trigger workflow_dispatch
    trigger_workflow_dispatch() {
      curl -X POST \
        -H "Accept: application/vnd.github.v3+json" \
        -H "Authorization: token ${GITHUB_TOKEN}" \
        https://api.github.com/repos/${REPO_OWNER}/${REPO_NAME}/actions/workflows/${WORKFLOW_ID_ESML}/dispatches \
        -d "{\"ref\":\"${REF}\",\"inputs\":{\"default\":\"${DEFAULT_ENV}\"}}"
    }

else
    echo -e "${RED} Unknown project type: ${PROJECT_TYPE} ${NC}"
fi