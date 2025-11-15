
.PHONY: build clean

build:
	@echo "building wheel in $(SUBDIR)"
	rm -rf dist
	pip install --upgrade setuptools wheel
	pip install -r requirements.txt
	python setup.py bdist_wheel

clean:
	rm -rf dist

