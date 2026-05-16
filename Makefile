PYTHON ?= python3
PIP ?= $(PYTHON) -m pip
OS_NAME := $(shell uname -s 2>/dev/null || echo Windows)

.PHONY: install run test lint format

install:
ifeq ($(OS_NAME),Darwin)
	$(PIP) install -r requirements-darwin.txt
else ifeq ($(OS_NAME),Linux)
	$(PIP) install -r requirements-linux.txt
else
	$(PIP) install -r requirements-windows.txt
endif

run:
	$(PYTHON) -m src.main

test:
	$(PYTHON) -m pytest tests/ -v --cov=src --cov-report=term-missing --cov-fail-under=80

lint:
	$(PYTHON) -m ruff check src/ tests/
	$(PYTHON) -m ruff format --check src/ tests/

format:
	$(PYTHON) -m ruff format src/ tests/
	$(PYTHON) -m ruff check --fix src/ tests/

