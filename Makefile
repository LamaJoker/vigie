# Raccourcis pour les tâches courantes. « make aide » liste les commandes.

VENV := .venv
BIN := $(VENV)/bin

# Base PostgreSQL de développement : lancée à la demande dans .pgdata/,
# joignable uniquement par un fichier socket (aucun port réseau ouvert).
PGBIN := $(shell ls -d /usr/lib/postgresql/*/bin 2>/dev/null | sort -V | tail -1)
PGDATA := $(CURDIR)/.pgdata
PGPORT := 5433
BASE_DEV := postgresql://vigie@/vigie?host=$(PGDATA)&port=$(PGPORT)

# Secrets locaux (webhook Discord...) : lus dans .env s'il existe, jamais commité.
-include .env
export VIGIE_DISCORD_WEBHOOK

.PHONY: aide installer tests tests-python tests-bash lint format sonder serveur \
	db-demarrer db-arreter tester-alerte docker-secrets docker-demarrer docker-arreter \
	docker-etat docker-journaux lint-docker tests-docker

aide:
	@echo "make installer     crée l'environnement virtuel et installe Vigie"
	@echo "make tests         lance tous les tests (Python et Bash)"
	@echo "make lint          vérifie le style et la qualité du code"
	@echo "make format        met le code Python en forme"
	@echo "make db-demarrer   lance la base PostgreSQL de développement"
	@echo "make sonder        teste les sites et enregistre les résultats en base"
	@echo "make serveur       lance la page de statut sur http://127.0.0.1:8000"
	@echo "make db-arreter    arrête la base de développement"
	@echo "make tester-alerte envoie une alerte d'essai sur Discord (voir .env.exemple)"
	@echo ""
	@echo "En conteneurs (Docker) :"
	@echo "make docker-demarrer  construit l'image et lance base, API et sonde"
	@echo "make docker-etat      état des conteneurs et de leurs contrôles de santé"
	@echo "make docker-journaux  suit les journaux des conteneurs"
	@echo "make docker-arreter   arrête les conteneurs (les données sont gardées)"
	@echo "make lint-docker      vérifie le Dockerfile (hadolint) et compose.yaml"
	@echo "make tests-docker     essai de bout en bout de la pile, dans un projet jetable"

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
	shellcheck sonde/*.sh tests/docker/*.sh

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

tester-alerte: installer
	$(BIN)/vigie tester-alerte

# Crée .env si besoin et y ajoute un mot de passe aléatoire pour la base des conteneurs.
docker-secrets:
	@touch .env && chmod 600 .env
	@grep -q '^VIGIE_MOT_DE_PASSE_BASE=.' .env || { \
		sed -i '/^VIGIE_MOT_DE_PASSE_BASE=$$/d' .env; \
		echo "VIGIE_MOT_DE_PASSE_BASE=$$(python3 -c 'import secrets; print(secrets.token_hex(24))')" >> .env; \
		echo "Mot de passe de la base créé dans .env"; }

docker-demarrer: docker-secrets
	docker compose build
	docker compose up -d
	@echo "Vigie démarre : http://localhost:$${VIGIE_PORT:-8000} (make docker-etat pour suivre)"

docker-arreter:
	docker compose down

docker-etat:
	docker compose ps

docker-journaux:
	docker compose logs --follow --tail=50

lint-docker:
	docker run --rm -i hadolint/hadolint:latest-debian < Dockerfile
	VIGIE_MOT_DE_PASSE_BASE=verification docker compose config --quiet
	@echo "Dockerfile et compose.yaml : aucun problème"

tests-docker:
	tests/docker/essai-pile.sh
