#!/usr/bin/env bash
# Installe uv, le gestionnaire de dépendances Python du projet, dans ~/.local/bin.
#
# Pas de « curl | sh » : on télécharge une version précise de l'archive officielle, on
# vérifie son empreinte SHA-256, écrite ci-dessous une fois pour toutes, puis on l'extrait.
# Si l'archive a été modifiée, même d'un octet, l'installation s'arrête.
#
# Pour changer de version : mettre à jour VERSION et EMPREINTE (page de la version sur
# https://github.com/astral-sh/uv/releases), ainsi que required-version dans
# pyproject.toml et l'image uv du Dockerfile.

set -euo pipefail

VERSION=0.13.8
CIBLE=x86_64-unknown-linux-gnu
EMPREINTE=5acfd9177cfecf0bf87578f059728215ccc884388988f55f7a65041b57387d91
DESTINATION=${UV_DESTINATION:-$HOME/.local/bin}

if [[ $(uname -sm) != "Linux x86_64" ]]; then
  echo "installer-uv : prévu pour Linux x86_64 seulement (ici : $(uname -sm))" >&2
  exit 1
fi

if [[ -x $DESTINATION/uv ]] && [[ $("$DESTINATION/uv" --version) == "uv $VERSION"* ]]; then
  echo "uv $VERSION est déjà installé dans $DESTINATION"
  exit 0
fi

dossier=$(mktemp -d)
trap 'rm -rf "$dossier"' EXIT
archive="$dossier/uv-$CIBLE.tar.gz"
adresse="https://github.com/astral-sh/uv/releases/download/$VERSION/uv-$CIBLE.tar.gz"

echo "Téléchargement de uv $VERSION..."
curl --fail --silent --show-error --location --proto '=https' --tlsv1.2 \
  --output "$archive" "$adresse"

if ! echo "$EMPREINTE  $archive" | sha256sum --check --status; then
  echo "installer-uv : EMPREINTE INATTENDUE, archive refusée" >&2
  echo "  attendue : $EMPREINTE" >&2
  echo "  obtenue  : $(sha256sum "$archive" | cut -d' ' -f1)" >&2
  exit 1
fi
echo "Empreinte vérifiée : $EMPREINTE"

tar --extract --gzip --file "$archive" --directory "$dossier" --strip-components 1
mkdir -p "$DESTINATION"
install -m 0755 "$dossier/uv" "$dossier/uvx" "$DESTINATION/"
echo "Installé : $("$DESTINATION/uv" --version) dans $DESTINATION"
