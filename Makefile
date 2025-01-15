# SPDX-FileCopyrightText: 2023–2024 Lukas Krodinger <lukas.krodinger@uni-passau.de>
#
# SPDX-License-Identifier: EUPL-1.2

SHELL := /usr/bin/env bash

ifeq ($(STRICT), 1)
	POETRY_COMMAND_FLAG =
	PIP_COMMAND_FLAG =
	SECRETS_COMMAND_FLAG =
	BLACK_COMMAND_FLAG =
	ISORT_COMMAND_FLAG =
	MYPY_COMMAND_FLAG =
else
	POETRY_COMMAND_FLAG = -
	PIP_COMMAND_FLAG = -
	SECRETS_COMMAND_FLAG = -
	BLACK_COMMAND_FLAG = -
	ISORT_COMMAND_FLAG = -
	MYPY_COMMAND_FLAG = -
endif

ifeq ($(POETRY_STRICT), 1)
	POETRY_COMMAND_FLAG =
else ifeq ($(POETRY_STRICT), 0)
	POETRY_COMMAND_FLAG = -
endif

ifeq ($(PIP_STRICT), 1)
	PIP_COMMAND_FLAG =
else ifeq ($(PIP_STRICT), 0)
	PIP_COMMAND_FLAG = -
endif

ifeq ($(SECRETS_STRICT), 1)
	SECRETS_COMMAND_FLAG =
else ifeq ($(SECRETS_STRICT), 0)
	SECRETS_COMMAND_FLAG = -
endif

ifeq ($(BLACK_STRICT), 1)
	BLACK_COMMAND_FLAG =
else ifeq ($(BLACK_STRICT), 0)
	BLACK_COMMAND_FLAG = -
endif

ifeq ($(ISORT_STRICT), 1)
	ISORT_COMMAND_FLAG =
else ifeq ($(ISORT_STRICT), 0)
	ISORT_COMMAND_FLAG = -
endif

ifeq ($(MYPY_STRICT), 1)
	MYPY_COMMAND_FLAG =
else ifeq ($(MYPY_STRICT), 0)
	MYPY_COMMAND_FLAG = -
endif


.PHONY: download-poetry
download-poetry:
	curl -sSL https://install.python-poetry.org | python3 -

.PHONY: install
install:
	poetry lock -n
	poetry install -n
ifneq ($(NO_PRE_COMMIT), 1)
	poetry run pre-commit install
endif

.PHONY: clean
clean:
	find . -type d -name "__pycache__" -exec rm -r {} +
	find . -type d -name ".mypy_cache" -exec rm -r {} +
	find . -type d -name "output" -exec rm -r {} +
	rm -rf .pytest_cache .ruff_cache

.PHONY: check-safety
check-safety:
	$(POETRY_COMMAND_FLAG)poetry check
	$(PIP_COMMAND_FLAG)pip check

.PHONY: check-style
check-style:
	$(BLACK_COMMAND_FLAG)poetry run black --diff --check ./
	$(ISORT_COMMAND_FLAG)poetry run isort --check-only .
	$(MYPY_COMMAND_FLAG)poetry run mypy src/
	$(POETRY_COMMAND_FLAG)poetry run ruff check --config ./pyproject.toml

.PHONY: pyupgrade
pyupgrade:
	poetry run pyupgrade --py313-plus $(shell find ./src -name "*.py") $(shell find ./tests -name "*.py")

.PHONY: codestyle
codestyle:
	poetry run pre-commit run --all-files

.PHONY: test
test:
	poetry run pytest --cov=src --cov=tests --cov-report=term-missing --cov-report=html:cov_html tests/

.PHONY: mypy
mypy:
	poetry run mypy src/

.PHONY: ruff
ruff:
	poetry run ruff check src/strds --fix --config ./pyproject.toml

.PHONY: isort
isort:
	poetry run isort .

.PHONY: black
black:
	poetry run black .

.PHONY: pylint
pylint:
	poetry run pylint src/

.PHONY: check
check: isort black mypy ruff pyupgrade test

.PHONY: lint
lint: test check-safety check-style pylint
