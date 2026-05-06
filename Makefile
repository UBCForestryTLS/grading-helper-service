build-ApiFunction:
	powershell -Command "Copy-Item -Recurse src $(ARTIFACTS_DIR)/src"
	python -m pip install \
		--platform manylinux2014_x86_64 \
		--only-binary=:all: \
		--implementation cp \
		--python-version 3.11\
		-r requirements.txt \
		-t $(ARTIFACTS_DIR)/
