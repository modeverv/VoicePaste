PYTHON ?= python3
PIP ?= $(PYTHON) -m pip
OS_NAME := $(shell uname -s 2>/dev/null || echo Windows)

.PHONY: install run run-gui mic-test test lint format

install:
ifeq ($(OS_NAME),Darwin)
	$(PIP) install -r requirements-darwin.txt
else ifeq ($(OS_NAME),Linux)
	$(PIP) install -r requirements-linux.txt
else
	$(PIP) install -r requirements-windows.txt
endif
	$(PYTHON) -m src.download

run:
	$(PYTHON) -m src.main

run-gui:
	$(PYTHON) -m src.gui

mic-test:
	DEVICE="$(DEVICE)" SECONDS="$(SECONDS)" $(PYTHON) -m src.mic_check

test:
	$(PYTHON) -m pytest tests/ -v --cov=src --cov-report=term-missing --cov-fail-under=80

lint:
	$(PYTHON) -m ruff check src/ tests/
	$(PYTHON) -m ruff format --check src/ tests/

format:
	$(PYTHON) -m ruff format src/ tests/
	$(PYTHON) -m ruff check --fix src/ tests/
