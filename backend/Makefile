RESOURCE_GROUP = QuickScribeResourceGroup
APP_NAME = QuickScribeFunctionApp

bump_version:
	bump2version --allow-dirty patch
	
copy_shared:
	rm -rf shared
	mkdir shared
	cp -r ../shared/* shared/
	cp ../shared/.env .env

deploy_azure: copy_shared
	@echo "Ensure that you are logged in to the Azure CLI *AND* that you have elevated your permissions to the Contributor."
	pip freeze > requirements.txt
	func azure functionapp publish $(APP_NAME) --build-remote

test_cloud:
	python test_function.py cloud api_version

start_local: copy_shared
	func start --port 7071

test_local:
	python test_function.py local api_version

deploy_to_test: copy_shared
	@echo "deploy_to_test is currently not supported"

deploy: deploy_azure