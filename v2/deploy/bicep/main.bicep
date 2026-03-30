// QuickScribe v2 — Azure infrastructure
// Deploys: App Service Plan, Container Registry, Storage Account, Web App

@description('Azure region for all resources')
param location string = resourceGroup().location

@description('App Service Plan name')
param appServicePlanName string

@description('Web App name (globally unique)')
param webAppName string

@description('Container Registry name (globally unique, alphanumeric only)')
param acrName string

@description('Storage Account name (globally unique, lowercase alphanumeric only)')
param storageAccountName string

@description('Blob container name for Litestream backups')
param blobContainerName string = 'quickscribe-backup'

@description('Docker image name')
param imageName string = 'quickscribe-v2'

@description('App Service Plan SKU')
param appSku string = 'B3'

@description('Port the app listens on')
param appPort string = '8000'

@description('Database path inside the container')
param dbPath string = '/app/data/app.db'

// --- App Service Plan ---
resource appServicePlan 'Microsoft.Web/serverfarms@2023-01-01' = {
  name: appServicePlanName
  location: location
  kind: 'linux'
  properties: {
    reserved: true
  }
  sku: {
    name: appSku
    capacity: 1  // CRITICAL: SQLite + Litestream requires exactly 1 instance. Never scale out.
  }
}

// --- Container Registry ---
resource acr 'Microsoft.ContainerRegistry/registries@2023-07-01' = {
  name: acrName
  location: location
  sku: {
    name: 'Basic'
  }
  properties: {
    adminUserEnabled: true
  }
}

// --- Storage Account ---
resource storageAccount 'Microsoft.Storage/storageAccounts@2023-05-01' = {
  name: storageAccountName
  location: location
  sku: {
    name: 'Standard_LRS'
  }
  kind: 'StorageV2'
  properties: {
    allowBlobPublicAccess: false
    minimumTlsVersion: 'TLS1_2'
  }
}

resource blobService 'Microsoft.Storage/storageAccounts/blobServices@2023-05-01' = {
  parent: storageAccount
  name: 'default'
}

resource blobContainer 'Microsoft.Storage/storageAccounts/blobServices/containers@2023-05-01' = {
  parent: blobService
  name: blobContainerName
}

// --- Web App ---
resource webApp 'Microsoft.Web/sites@2023-01-01' = {
  name: webAppName
  location: location
  properties: {
    serverFarmId: appServicePlan.id
    httpsOnly: true
    siteConfig: {
      linuxFxVersion: 'DOCKER|${acr.properties.loginServer}/${imageName}:latest'
      alwaysOn: true
      healthCheckPath: '/api/health'
      appSettings: [
        { name: 'WEBSITES_PORT', value: appPort }
        { name: 'DOCKER_REGISTRY_SERVER_URL', value: 'https://${acr.properties.loginServer}' }
        { name: 'DOCKER_REGISTRY_SERVER_USERNAME', value: acr.listCredentials().username }
        { name: 'DOCKER_REGISTRY_SERVER_PASSWORD', value: acr.listCredentials().passwords[0].value }
        { name: 'WEBSITES_ENABLE_APP_SERVICE_STORAGE', value: 'false' }
        { name: 'DATABASE_PATH', value: dbPath }
        { name: 'AZURE_STORAGE_ACCOUNT', value: storageAccount.name }
        { name: 'AZURE_STORAGE_KEY', value: storageAccount.listKeys().keys[0].value }
        { name: 'LITESTREAM_BUCKET', value: blobContainerName }
        { name: 'WEBSITES_CONTAINER_START_TIME_LIMIT', value: '1800' }
      ]
    }
  }
}

// --- Outputs ---
output webAppUrl string = 'https://${webApp.properties.defaultHostName}'
output acrLoginServer string = acr.properties.loginServer
output storageAccountName string = storageAccount.name
