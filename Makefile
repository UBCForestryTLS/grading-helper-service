build-ApiFunction:
	cp -r src $(ARTIFACTS_DIR)/src
	python3.13 -m pip install \
		--platform manylinux2014_aarch64 \
		--only-binary=:all: \
		--implementation cp \
		--python-version 3.13 \
		-r requirements.txt \
		-t $(ARTIFACTS_DIR)/
