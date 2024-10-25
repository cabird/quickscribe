RESOURCE_GROUP = QuickScribeResourceGroup
APP_NAME = QuickScribeWebApp
SPEECH_CLIENT_DIR = azure_speech/python-client

.PHONY: build_packages bump_version build_zip clean

build_packages:
	$(MAKE) -C $(SPEECH_CLIENT_DIR) build
	mkdir -p local_packages
	cp $(SPEECH_CLIENT_DIR)/dist/*whl local_packages

bump_version:
	bump2version --allow-dirty patch
	@cat api_version.py

build_zip: build_packages
	rm -f app.zip
	pip freeze > requirements.txt
	python generate_filelist.py
	zip app.zip -@ < filelist.txt

deploy_azure: build_zip
	@echo "Ensure that you are logged in to the Azure CLI *AND* that you have elevated your permissions to the Contributor."
	# set an app setting to force a build during deployment
	az webapp config appsettings set --name $(APP_NAME) --resource-group $(RESOURCE_GROUP) --settings SCM_DO_BUILD_DURING_DEPLOYMENT=false
	az webapp deploy --name $(APP_NAME) --resource-group $(RESOURCE_GROUP) --type zip --src-path app.zip

deploy_to_test: build_zip
	@echo "Ensure that you are logged in to the Azure CLI *AND* that you have elevated your permissions to the Contributor."
	# set an app setting to force a build during deployment
	az webapp config appsettings set --name $(APP_NAME) --resource-group $(RESOURCE_GROUP) --slot test --settings SCM_DO_BUILD_DURING_DEPLOYMENT=false
	az webapp deploy --name $(APP_NAME) --resource-group $(RESOURCE_GROUP) --slot test --type zip --src-path app.zip

deploy: deploy_azure

clean:
	$(MAKE) -C $(SPEECH_CLIENT_DIR) clean
	rm -rf local_packages
	rm -rf app.zip
	rm -rf filelist.txt
