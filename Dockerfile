# syntax=docker/dockerfile:1
# Image de Vigie, construite en deux étapes :
#   1. « construction » installe Vigie et ses dépendances dans un environnement virtuel ;
#   2. « execution » ne recopie que cet environnement : pas d'outils de construction,
#      pas de code source en trop, et un utilisateur sans droits d'administration.

ARG PYTHON_VERSION=3.14

# ---------------------------------------------------------------- construction
FROM python:${PYTHON_VERSION}-slim AS construction

ENV PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

RUN python -m venv /opt/vigie
WORKDIR /construction

# Les fichiers qui changent le moins en premier : Docker réutilise les étapes
# déjà construites tant que leurs fichiers n'ont pas bougé (cache des couches).
COPY pyproject.toml README.md ./
COPY src ./src
RUN /opt/vigie/bin/pip install .

# ------------------------------------------------------------------- execution
FROM python:${PYTHON_VERSION}-slim AS execution

LABEL org.opencontainers.image.title="Vigie" \
      org.opencontainers.image.description="Surveillance de sites web : sonde, API, page de statut, alertes" \
      org.opencontainers.image.source="https://github.com/LamaJoker/vigie"

ENV PATH=/opt/vigie/bin:$PATH \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    VIGIE_CONFIG=/etc/vigie/vigie.toml \
    VIGIE_LOG=/var/lib/vigie/sondes.jsonl

# Utilisateur dédié, sans mot de passe ni droits root. Son numéro (UID) est fixé :
# Kubernetes s'en sert pour vérifier qu'un conteneur ne tourne pas en root.
ARG UID=10001
RUN groupadd --system --gid "${UID}" vigie \
    && useradd --system --uid "${UID}" --gid vigie --home-dir /var/lib/vigie --create-home \
       --shell /usr/sbin/nologin vigie

COPY --from=construction /opt/vigie /opt/vigie
COPY config/vigie.toml /etc/vigie/vigie.toml

USER ${UID}:${UID}
WORKDIR /var/lib/vigie
EXPOSE 8000

# Forme « exec » (tableau JSON) : vigie est le processus n°1 du conteneur et reçoit
# directement le signal d'arrêt envoyé par « docker stop ».
ENTRYPOINT ["vigie"]
CMD ["serveur", "--hote", "0.0.0.0"]
