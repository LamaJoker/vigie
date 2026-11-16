# Image de Vigie, construite en deux étapes :
#   1. « construction » installe Vigie et ses dépendances dans un environnement virtuel,
#      aux versions exactes de uv.lock, l'empreinte de chaque paquet étant vérifiée ;
#   2. « execution » ne recopie que cet environnement : pas d'outils de construction,
#      pas de code source en trop, et un utilisateur sans droits d'administration.
#
# Chaque image de départ est désignée par son empreinte (@sha256:...) et pas seulement
# par son étiquette, qui peut être déplacée vers un autre contenu (décision 0007).
# Dependabot propose chaque semaine les nouvelles versions.

# ------------------------------------------------------------------------- uv
# Image officielle de uv, dont on ne prend que le programme. Même version que
# required-version dans pyproject.toml.
FROM ghcr.io/astral-sh/uv:0.13.8@sha256:5cc1805e2426484abca4ad46ea783bab281fdb225fd82d8ce6d66a81254bac85 AS uv

# ---------------------------------------------------------------- construction
FROM python:3.15-slim@sha256:65a65fc7b30b06cb6df4930fd4650697cb23f4c2698ab81fc87e4b031bc36928 AS construction

COPY --from=uv /uv /usr/local/bin/uv

# Environnement virtuel dans /opt/vigie, avec le Python de l'image (jamais téléchargé),
# fichiers Python compilés d'avance, et sans cache (il ne servirait qu'une fois).
ENV UV_PROJECT_ENVIRONMENT=/opt/vigie \
    UV_PYTHON_DOWNLOADS=never \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_NO_CACHE=1
WORKDIR /construction

# D'abord les dépendances seules : Docker garde cette étape en cache tant que le verrou
# ne change pas. « --locked » refuse un verrou qui ne correspond plus à pyproject.toml,
# et uv refuse tout paquet dont l'empreinte diffère de celle du verrou.
COPY pyproject.toml uv.lock ./
RUN uv sync --locked --no-dev --no-install-project

# Puis Vigie elle-même, installée comme un paquet ordinaire (pas un lien vers les sources).
COPY README.md ./
COPY src ./src
RUN uv sync --locked --no-dev --no-editable

# ------------------------------------------------------------------- execution
FROM python:3.15-slim@sha256:65a65fc7b30b06cb6df4930fd4650697cb23f4c2698ab81fc87e4b031bc36928 AS execution

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
