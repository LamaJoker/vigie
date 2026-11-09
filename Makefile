# Raccourcis pour les tâches courantes. « make aide » liste les commandes.

VENV := .venv
BIN := $(VENV)/bin

# Base PostgreSQL de développement : lancée à la demande dans .pgdata/,
# joignable uniquement par un fichier socket (aucun port réseau ouvert).
PGBIN := $(shell ls -d /usr/lib/postgresql/*/bin 2>/dev/null | sort -V | tail -1)
PGDATA := $(CURDIR)/.pgdata
PGPORT := 5433
BASE_DEV := postgresql://vigie@/vigie?host=$(PGDATA)&port=$(PGPORT)

.PHONY: aide installer tests tests-python tests-bash lint format sonder serveur db-demarrer db-arreter

aide:
	@echo "make installer     crée l'environnement virtuel et installe Vigie"
	@echo "make tests         lance tous les tests (Python et Bash)"
	@echo "make lint          vérifie le style et la qualité du code"
	@echo "make format        met le code Python en forme"
	@echo "make db-demarrer   lance la base PostgreSQL de développement"
	@echo "make sonder        teste les sites et enregistre les résultats en base"
	@echo "make serveur       lance la page de statut sur http://127.0.0.1:8000"
	@echo "make db-arreter    arrête la base de développement"

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

db-demarrer: installer
	@test -n "$(PGBIN)" || { echo "PostgreSQL n'est pas installé : sudo apt install postgresql"; exit 1; }
	@test -d $(PGDATA) || $(PGBIN)/initdb -D $(PGDATA) -U vigie --auth=trust -E UTF8 >/dev/null
	@$(PGBIN)/pg_ctl -D $(PGDATA) status >/dev/null || \
		$(PGBIN)/pg_ctl -D $(PGDATA) -l $(PGDATA)/pg.log -w \
		-o "-p $(PGPORT) -k $(PGDATA) -c listen_addresses=''" start
	@$(PGBIN)/psql -h $(PGDATA) -p $(PGPORT) -U vigie -d postgres -tAc \
		"SELECT 1 FROM pg_database WHERE datname = 'vigie'" | grep -q 1 || \
		$(PGBIN)/createdb -h $(PGDATA) -p $(PGPORT) -U vigie vigie
	@VIGIE_DATABASE_URL='$(BASE_DEV)' $(BIN)/vigie init-db

db-arreter:
	@$(PGBIN)/pg_ctl -D $(PGDATA) status >/dev/null && $(PGBIN)/pg_ctl -D $(PGDATA) -m fast stop || \
		echo "La base de développement est déjà arrêtée."

sonder: installer
	VIGIE_DATABASE_URL='$(BASE_DEV)' $(BIN)/vigie sonder

serveur: installer
	VIGIE_DATABASE_URL='$(BASE_DEV)' $(BIN)/vigie serveur
