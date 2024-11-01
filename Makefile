SPHINXOPTS    ?=
SPHINXBUILD   ?= sphinx-build
SOURCEDIR     = debgpt
BUILDDIR      = _build

main: pytest

man: debgpt.1

.PHONY: debgpt.1
debgpt.1:
	pandoc -s README.md -t man > $@

autopep8:
	@echo autopep8 is deprecated, use yapf instead
	#find debgpt -type f -name '*.py' -exec autopep8 -i '{}' \;
	$(MAKE) yapf

yapf:
	find debgpt -type f -name '*.py' -exec yapf -i '{}' \;

pytest:
	PYTHONPATH=. pytest --cov=debgpt --cov-report=html -v

lint:
	find . -type f -name '*.py' -exec pyflakes '{}' \;
	find . -type f -name '*.py' -exec pylint '{}' \;

install:
	pip3 install .

doc:
	sphinx-apidoc -o . debgpt
	sphinx-build . html
