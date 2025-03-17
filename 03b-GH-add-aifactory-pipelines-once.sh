#!/bin/bash

# ANSI color codes
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

################### VARIABLES ###################
use_gha_bicep=true

use_gha_terraform=false
use_ado_bicep=false
################### VARIABLES ###################

# 01. Setup and Preparation

# DIRECTORIES
current_dir=$(pwd)
aif_dir="$current_dir/aifactory"
gha_bicep_dir="$aif_dir/esml-infra/github-actions/bicep/"
gha_workflow_dir=".github/workflows"

# Delete & Re-Create the workflow directory
rm -rf "$gha_workflow_dir"
mkdir -p "$gha_workflow_dir"

# Copy workflows
if [ "$use_gha_bicep" = true ]; then
    echo -e "${YELLOW}01. Copy pipelines to $gha_workflow_dir ${NC}"
    mkdir -p $gha_workflow_dir
    cp "$gha_bicep_dir" "$gha_workflow_dir" -r
fi