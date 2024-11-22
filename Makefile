SPHINXOPTS    ?=
SPHINXBUILD   ?= sphinx-build
SOURCEDIR     = debgpt
BUILDDIR      = _build

main: pytest

man: debgpt.1

.PHONY: debgpt.1
debgpt.1:
	pandoc -s README.md -t man > $@

yapf:
	find debgpt -type f -name '*.py' -exec yapf -i '{}' \;
	find tests -type f -name '*.py' -exec yapf -i '{}' \;

pytest:
	PYTHONPATH=. pytest --durations=10 --cov=debgpt --cov-report=html -v -n 8 $(ARGS)
	-open -a safari htmlcov/index.html

lint:
	find . -type f -name '*.py' -exec pyflakes '{}' \;
	find . -type f -name '*.py' -exec pylint '{}' \;
	pytype debgpt -j auto

install:
	pip3 install .

doc:
	sphinx-apidoc -o . debgpt
	sphinx-build . html
