RESOURCE_GROUP = QuickScribeResourceGroup
APP_NAME = QuickScribeWebApp

bump_version:
	bump2version --allow-dirty patch

build_zip:
	pip freeze > requirements.txt
	python generate_filelist.py
	zip app.zip -@ < filelist.txt

deploy_azure: build_zip
	@echo "Ensure that you are logged in to the Azure CLI *AND* that you have elevated your permissions to the Contributor."
	# set an app setting to force a build during deployment
	az webapp config appsettings set --name $(APP_NAME) --resource-group $(RESOURCE_GROUP) --settings SCM_DO_BUILD_DURING_DEPLOYMENT=true
	az webapp deploy --name $(APP_NAME) --resource-group $(RESOURCE_GROUP) --type zip --src-path app.zip

deploy_to_test: build_zip
	@echo "Ensure that you are logged in to the Azure CLI *AND* that you have elevated your permissions to the Contributor."
	# set an app setting to force a build during deployment
	az webapp config appsettings set --name $(APP_NAME) --resource-group $(RESOURCE_GROUP) --slot test --settings SCM_DO_BUILD_DURING_DEPLOYMENT=true
	az webapp deploy --name $(APP_NAME) --resource-group $(RESOURCE_GROUP) --slot test --type zip --src-path app.zip

deploy: deploy_azure
