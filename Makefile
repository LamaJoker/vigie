# Raccourcis pour les tâches courantes. « make aide » liste les commandes.

VENV := .venv
BIN := $(VENV)/bin
# uv installe les dépendances aux versions exactes de uv.lock. S'il manque :
# scripts/installer-uv.sh (version fixée, empreinte vérifiée).
UV := $(or $(shell command -v uv 2>/dev/null),$(HOME)/.local/bin/uv)

# Images des outils d'analyse, désignées par leur empreinte : une étiquette comme
# « latest » peut changer de contenu à tout moment (docs/decisions/0007).
IMAGE_HADOLINT := hadolint/hadolint:v2.15.1-debian@sha256:9a3944b7fddcb947d1ffd90829ac1a6e5c30479223358f249d8b96c7d0019e27
IMAGE_ACTIONLINT := rhysd/actionlint:1.7.12@sha256:b1934ee5f1c509618f2508e6eb47ee0d3520686341fec936f3b79331f9315667

# Base PostgreSQL de développement : lancée à la demande dans .pgdata/,
# joignable uniquement par un fichier socket (aucun port réseau ouvert).
PGBIN := $(shell ls -d /usr/lib/postgresql/*/bin 2>/dev/null | sort -V | tail -1)
PGDATA := $(CURDIR)/.pgdata
PGPORT := 5433
BASE_DEV := postgresql://vigie@/vigie?host=$(PGDATA)&port=$(PGPORT)

# Secrets locaux (webhook Discord...) : lus dans .env s'il existe, jamais commité.
-include .env
export VIGIE_DISCORD_WEBHOOK

.PHONY: aide installer verrouiller tests tests-python tests-bash lint format sonder serveur \
	db-demarrer db-arreter tester-alerte docker-secrets docker-demarrer docker-arreter \
	docker-etat docker-journaux lint-docker tests-docker lint-ci ci

aide:
	@echo "make installer     crée l'environnement virtuel et installe Vigie (versions de uv.lock)"
	@echo "make verrouiller   recalcule uv.lock après une modification de pyproject.toml"
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
	@echo ""
	@echo "make ci               toutes les vérifications de l'intégration continue, en local"

installer: $(VENV)/.installe

# « --locked » : refuse de travailler si uv.lock ne correspond plus à pyproject.toml.
$(VENV)/.installe: pyproject.toml uv.lock
	@test -x "$(UV)" || { echo "uv n'est pas installé : lancer scripts/installer-uv.sh"; exit 1; }
	$(UV) sync --locked --quiet
	touch $@

# Après avoir modifié les dépendances de pyproject.toml. Pour monter de version sans
# changer pyproject.toml : uv lock --upgrade (Dependabot le propose chaque semaine).
verrouiller:
	$(UV) lock

tests: tests-python tests-bash

tests-python: installer
	$(BIN)/pytest

tests-bash:
	bats tests/bash/

lint: installer
	$(UV) lock --check
	$(BIN)/ruff check .
	$(BIN)/ruff format --check .
	shellcheck sonde/*.sh tests/docker/*.sh scripts/*.sh
	$(BIN)/python scripts/verifier_liens.py
	$(BIN)/python scripts/verifier_epinglage.py

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
	@VIGIE_DATABASE_URL='$(BASE_DEV)' $(BIN)/vigie migrer

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
	docker run --rm -i $(IMAGE_HADOLINT) < Dockerfile
	VIGIE_MOT_DE_PASSE_BASE=verification docker compose config --quiet
	@echo "Dockerfile et compose.yaml : aucun problème"

tests-docker:
	tests/docker/essai-pile.sh

# Vérifie la syntaxe et les pièges courants des workflows GitHub Actions.
lint-ci:
	docker run --rm -v "$(CURDIR):/depot:ro" -w /depot $(IMAGE_ACTIONLINT) -color

# Les mêmes vérifications que GitHub Actions, sur le poste, avant de pousser.
ci: lint lint-docker lint-ci tests tests-docker
	@echo "Toutes les vérifications de l'intégration continue sont passées."
