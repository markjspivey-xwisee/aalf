#!/bin/bash
# Deploy AALF to Azure App Service
# Prerequisites: az cli logged in, npm installed

set -e

RESOURCE_GROUP="aalf-rg"
APP_NAME="aalf-game"
LOCATION="eastus"
SKU="F1"  # Free tier

echo "=== AALF Azure Deployment ==="

# 1. Create resource group
echo "Creating resource group..."
az group create --name $RESOURCE_GROUP --location $LOCATION --output none 2>/dev/null || true

# 2. Create App Service plan (free tier)
echo "Creating App Service plan..."
az appservice plan create --name "${APP_NAME}-plan" --resource-group $RESOURCE_GROUP --sku $SKU --is-linux --output none 2>/dev/null || true

# 3. Create web app with Node.js
echo "Creating web app..."
az webapp create --name $APP_NAME --resource-group $RESOURCE_GROUP --plan "${APP_NAME}-plan" --runtime "NODE:18-lts" --output none 2>/dev/null || true

# 4. Enable WebSockets
echo "Enabling WebSockets..."
az webapp config set --name $APP_NAME --resource-group $RESOURCE_GROUP --web-sockets-enabled true --output none

# 5. Set startup command
az webapp config set --name $APP_NAME --resource-group $RESOURCE_GROUP --startup-file "cd server && npm install && npm start" --output none

# 6. Deploy via zip
echo "Packaging for deployment..."
cd "$(dirname "$0")"
# Create deployment package
mkdir -p /tmp/aalf-deploy
cp -r web server /tmp/aalf-deploy/
cd /tmp/aalf-deploy
zip -r /tmp/aalf-deploy.zip . -x "*.git*" "node_modules/*"

echo "Deploying to Azure..."
az webapp deploy --name $APP_NAME --resource-group $RESOURCE_GROUP --src-path /tmp/aalf-deploy.zip --type zip

# Cleanup
rm -rf /tmp/aalf-deploy /tmp/aalf-deploy.zip

echo ""
echo "=== DEPLOYED ==="
echo "URL: https://${APP_NAME}.azurewebsites.net"
echo "Multiplayer: https://${APP_NAME}.azurewebsites.net?seed=42"
echo ""
echo "To delete: az group delete --name $RESOURCE_GROUP --yes"
