# Raccourcis pour les tâches courantes. « make aide » liste les commandes.

VENV := .venv
BIN := $(VENV)/bin

.PHONY: aide installer tests tests-python tests-bash lint format sonder

aide:
	@echo "make installer   crée l'environnement virtuel et installe Vigie"
	@echo "make tests       lance tous les tests (Python et Bash)"
	@echo "make lint        vérifie le style et la qualité du code"
	@echo "make format      met le code Python en forme"
	@echo "make sonder      teste une fois les sites de config/vigie.toml"

installer: $(VENV)/.installe

$(VENV)/.installe: pyproject.toml
	python3 -m venv $(VENV)
	$(BIN)/pip install --quiet --upgrade pip
	$(BIN)/pip install --quiet -e ".[dev]"
	touch $@

tests: tests-python tests-bash

tests-python: installer
	$(BIN)/pytest

tests-bash:
	bats tests/bash/

lint: installer
	$(BIN)/ruff check .
	$(BIN)/ruff format --check .
	shellcheck sonde/*.sh

format: installer
	$(BIN)/ruff format .
	$(BIN)/ruff check --fix .

sonder: installer
	$(BIN)/vigie sonder
