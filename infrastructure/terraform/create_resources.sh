SUBSCRIPTION_ID=72f988bf-86f1-41af-91ab-2d7cd011db47

az group create --name QuickScribeResourceGroup --location westus2
az keyvault create --name QuickScribeKeyVault --resource-group QuickScribeResourceGroup --location westus2
az keyvault secret set --vault-name QuickScribeKeyVault --name AssemblyAIKey --value "$ASSEMBLYAI_API_KEY"
az storage account create \
    --name quickscribestorage \
    --resource-group QuickScribeResourceGroup \
    --location westus2 \
    --sku Standard_LRS \
    --kind StorageV2

az functionapp create \
    --resource-group QuickScribeResourceGroup \
    --consumption-plan-location westus2 \
    --runtime python \
    --runtime-version 3.11 \
    --functions-version 4 \
    --name QuickScribeFunctionApp \
    --storage-account quickscribestorage \
    --os-type Linux

az functionapp config appsettings set --name QuickScribeFunctionApp --resource-group QuickScribeResourceGroup --settings "KEY_VAULT_NAME=QuickScribeKeyVault"

func azure functionapp publish QuickScribeFunctionApp

az functionapp show --name QuickScribeFunctionApp --resource-group QuickScribeResourceGroup --query defaultHostName --output tsv

#create a user assigned managed identity
az identity create --name QuickScribeUAMI --resource-group QuickScribeResourceGroup --location westus2

az role assignment create \
  --role "AzureFunctionContributor" \
  --assignee /subscriptions/7da12d2b-bb26-497b-a28a-cdb64f11cfa3/resourceGroups/QuickScribeResourceGroup/providers/Microsoft.ManagedIdentity/userAssignedIdentities/QuickScribeUAMI \
  --scope /subscriptions/7da12d2b-bb26-497b-a28a-cdb64f11cfa3/resourceGroups/QuickScribeResourceGroup/providers/Microsoft.Web/sites/QuickScribeFunctionApp


#create the web app
az appservice plan create \
    --name QuickScribeAppServicePlan \
    --resource-group QuickScribeResourceGroup \
    --location westus \
    --sku B1 \
    --is-linux

az webapp create \
    --resource-group QuickScribeResourceGroup \
    --plan QuickScribeAppServicePlan \
    --name QuickScribeWebApp \
    --runtime "PYTHON:3.11" \

az webapp identity assign \
    --resource-group QuickScribeResourceGroup \
    --name QuickScribeWebApp \
    --identities /subscriptions/7da12d2b-bb26-497b-a28a-cdb64f11cfa3/resourceGroups/QuickScribeResourceGroup/providers/Microsoft.ManagedIdentity/userAssignedIdentities/QuickScribeUAMI

#put the azure functions key into the key vault
az keyvault secret set \
    --vault-name QuickScribeKeyVault \
    --name AzureFunctionKey \
    --value "$KEY"