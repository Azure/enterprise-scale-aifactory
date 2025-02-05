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

# 1) EDIT Variables ONCE ################### 
SUBSCRIPTION_ID=$AIFACTORY_SEEDING_KEYVAULT_SUBSCRIPTION_ID
KEY_VAULT_NAME=$AIFACTORY_SEEDING_KEYVAULT_NAME
TENANT_ID=$TENANT_ID
SERVICE_PRINCIPAL_NAME_TEMPLATE="esml-project[XXX]-sp"
PROJECT_NUMBER_Y="" # A number between 1-999
PROJECT_NUMBER_XXX="008" # A string with three characters: 001, 023, 123

# EDIT END

##################### DO NOT CHANGE ANYTHING BELOW #####################
# Template Names
SP_NAME_TEMPLATE="esml-projectXXX-sp-id"
SP_KV_ID_TEMPLATE="esml-projectXXX-sp-id"
SP_KV_OID_TEMPLATE="esml-projectXXX-sp-oid"
SP_KV_SECRET_TEMPLATE="esml-projectXXX-sp-secret"

# Replace "XXX" with the value in PROJECT_NUMBER_XXX
SERVICE_PRINCIPAL_NAME=""

if [[ $SERVICE_PRINCIPAL_NAME_TEMPLATE == *"[XXX]"* ]]; then
    echo "SERVICE_PRINCIPAL_NAME_TEMPLATE contains [XXX]"
    SERVICE_PRINCIPAL_NAME=$(echo $SERVICE_PRINCIPAL_NAME_TEMPLATE | sed "s/\[XXX\]/$PROJECT_NUMBER_XXX/")
elif [[ $SERVICE_PRINCIPAL_NAME_TEMPLATE == *"[Y]"* ]]; then
    echo "SERVICE_PRINCIPAL_NAME_TEMPLATE does not contains [Y]"
    SERVICE_PRINCIPAL_NAME=$(echo $SERVICE_PRINCIPAL_NAME_TEMPLATE | sed "s/\[Y\]/$PROJECT_NUMBER_XXX/")
fi

SP_KV_APP_ID=$(echo $SP_KV_ID_TEMPLATE | sed "s/XXX/$PROJECT_NUMBER_XXX/")
SP_KV_OID=$(echo $SP_KV_OID_TEMPLATE | sed "s/XXX/$PROJECT_NUMBER_XXX/")
SP_KV_SECRET=$(echo $SP_KV_SECRET_TEMPLATE | sed "s/XXX/$PROJECT_NUMBER_XXX/")

echo -e "${YELLOW}SERVICE_PRINCIPAL_NAME${NC} to be created is: ${GREEN}"$SERVICE_PRINCIPAL_NAME"${NC}"
echo -e "${YELLOW}APP ID name as KV SECRET${NC} in seeding keyvault will have the name: ${GREEN}"$SP_KV_APP_ID"${NC}"
echo -e "${YELLOW}OBJECT ID NAME as KV SECRET${NC} in seeding keyvault will have the name: ${GREEN}"$SP_KV_OID"${NC}"
echo -e "${YELLOW}SECRET NAME as KV SECRET${NC} in seeding keyvault will have the name: ${GREEN}"$SP_KV_SECRET"${NC}"
echo -e "${GREEN}Note: If exists: ${NC}If Service principla already exists, then ObjectID will be updated in seeding keyvault.${NC}"

# APPLICATIONS - To delete: Delete Application, and its service principal is also deleted.

#SP_OID='' # Set RBAC on this. Enterprise Application Object ID
#SP_APP_ID='' # Enterprise Application App_ID is same as APP_REG_ID
#APP_REG_OID='' # Set IMAGE on this. App Registration Object ID

# Prompt the user for confirmation
read -p "Continue (Y/n)? " choice
if [[ "$choice" == "n" || "$choice" == "N" ]]; then
    echo "Exiting script."
    exit 1
fi

# Login to Azure with EntraID user
echo -e "${YELLOW}Logging in to Azure...${NC}"
az login --tenant $TENANT_ID
az account set --subscription $SUBSCRIPTION_ID
#az account get-access-token

if [ $? -ne 0 ]; then
    echo -e "${RED}Failed to login to Azure${NC}"
    exit 1
fi

echo -e "${YELLOW}Checking if service principal exists...${NC}"
SP_EXISTS=$(az ad sp list --display-name "$SERVICE_PRINCIPAL_NAME" --query "[].appId" -o tsv)
APP_ID="not set"
OBJECT_ID="not set"
PASSWORD="not set"

if [ -z "$SP_EXISTS" ]; then
    echo -e "${YELLOW}Service principal does NOT exist${NC}"
    # Create service principal
    echo -e "${YELLOW}Creating service principal...${NC}"
    
    SP_OUTPUT=$(az ad sp create-for-rbac --name "$SERVICE_PRINCIPAL_NAME" --query "{appId: appId, password: password}" -o json)

    if [ $? -ne 0 ]; then
        echo -e "${RED}Failed to create service principal${NC}"
        exit 1
    fi
    # Echo all
    echo $SP_OUTPUT

    # Extract values
    APP_ID=$(echo $SP_OUTPUT | grep -oP '(?<="appId": ")[^"]*')
    PASSWORD=$(echo $SP_OUTPUT | grep -oP '(?<="password": ")[^"]*')
    OBJECT_ID=$(az ad sp show --id $APP_ID --query id -o tsv) # Set RBAC on this. Enterprise Application

    echo -e "${GREEN}Storing values (APP_ID, OID, SECRET) in Seeding Key Vault...${NC}"
    #Print APP_ID
    echo -e "${GREEN}APP_ID: {$APP_ID} ${NC}"
    echo -e "${GREEN}OBJECT_ID: {$OBJECT_ID} ${NC}"
    #echo -e "${GREEN}PASSWORD: {$PASSWORD} ${NC}"

    az keyvault secret set --vault-name $KEY_VAULT_NAME --name ${SP_KV_APP_ID} --value $APP_ID
    az keyvault secret set --vault-name $KEY_VAULT_NAME --name ${SP_KV_OID} --value $OBJECT_ID
    az keyvault secret set --vault-name $KEY_VAULT_NAME --name ${SP_KV_SECRET} --value $PASSWORD > /dev/null

    if [ $? -eq 0 ]; then
        echo -e "${GREEN}Service principal credentials stored in Key Vault successfully${NC}"
    else
        echo -e "${RED}Failed to store credentials in Key Vault${NC}"
        exit 1
    fi
else
    echo -e "${YELLOW}Service principal already exists. Now updating OBJECT_ID in Seeding Keyvault${NC}"
    APP_ID=$SP_EXISTS
    OBJECT_ID=$(az ad sp show --id $APP_ID --query id -o tsv) # Set RBAC on this. Enterprise Application

    #Print APP_ID
    echo -e "${GREEN}APP_ID: {$APP_ID} ${NC}"
    echo -e "${GREEN}OBJECT_ID: {$OBJECT_ID} ${NC}"
    #echo -e "${GREEN}PASSWORD: {$PASSWORD} ${NC}"
    
    az keyvault secret set --vault-name $KEY_VAULT_NAME --name ${SP_KV_OID} --value $OBJECT_ID
    az keyvault secret set --vault-name $KEY_VAULT_NAME --name ${SP_KV_APP_ID} --value $APP_ID
    
    if [ $? -eq 0 ]; then
        echo -e "${GREEN}Service principal credentials stored in Key Vault successfully${NC}"
    else
        echo -e "${RED}Failed to store credentials in Key Vault${NC}"
        exit 1
    fi
fi

# Set logo URL for the service principal

APP_REG_OID=$(az ad app show --id $APP_ID --query id --output tsv)
echo "APP_REG_OID: $APP_REG_OID"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOGO_URL="$SCRIPT_DIR/images/sp-aifactory-house.png"

if [ ! -f "$LOGO_URL" ]; then
    echo -e "${RED}Logo file not found at $LOGO_URL. Exiting...${NC}"
    exit 1
fi

echo -e "${YELLOW}Setting logo URL for the service principal...${NC}"

logo_content=$(base64 "$LOGO_URL")
token=$(az account get-access-token --resource https://graph.microsoft.com --query accessToken -o tsv)
curl -X PUT -H "Authorization: Bearer $token" -H "Content-Type: image/png" --data-binary "@$LOGO_URL" "https://graph.microsoft.com/v1.0/applications/$APP_REG_OID/logo"

if [ $? -eq 0 ]; then
    echo -e "${GREEN}Logo URL set successfully${NC}"
else
    echo -e "${RED}Failed to set logo URL${NC}"
    exit 1
fi