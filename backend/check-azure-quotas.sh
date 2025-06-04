#!/bin/bash
set -e  # Exit immediately if a command exits with a non-zero status

# This script allows you to check available regions and quotas before deploying

# List available regions for App Service Plans
echo "=== Available Regions for App Service Plans ==="
az appservice list-locations --sku FREE || echo "Error listing locations"
echo ""

# Check quota in specific regions
check_quota() {
    local region=$1
    local sku=$2
    echo "Checking quota for $sku in $region..."
    az vm list-usage --location $region --query "[?contains(name.value, 'standardBSFamily')]" -o table 2>/dev/null || echo "Unable to check quota in $region"
}

echo "=== Checking Quotas in Common Regions ==="
check_quota "eastus" "B1"
check_quota "centralus" "B1" 
check_quota "westus" "B1"
check_quota "westus2" "B1"

echo ""
echo "=== Recommendation ==="
echo "If you see quota issues, try deploying with these options:"
echo "./deploy-to-azure.sh --location eastus --sku F1"
echo ""
echo "You can also view your quota limits in the Azure Portal under:"
echo "Subscriptions > [Your subscription] > Usage + quotas"
