#!/usr/bin/env bash
# Vigie v0 : vérifie que des sites web répondent et enregistre le résultat.
#
# Utilisation : vigie.sh [fichier_des_sites]
#
# Variables d'environnement (facultatives) :
#   VIGIE_SITES  fichier des sites (défaut : sites.txt à côté de ce script)
#   VIGIE_LOG    fichier des résultats (défaut : ~/.local/state/vigie/sondes.log)
#   VIGIE_DELAI  temps maximal accordé à chaque site, en secondes (défaut : 10)
#
# Chaque ligne du log contient, séparés par des espaces :
#   date ISO 8601, état (UP ou DOWN), code HTTP (000 si pas de réponse),
#   temps de réponse en millisecondes, adresse testée.
#
# Code de sortie : 0 si tous les sites répondent, 1 si au moins un est en panne,
# 2 en cas d'erreur d'utilisation.

set -euo pipefail
export LC_ALL=C   # nombres avec un point décimal, quelle que soit la langue du système

DOSSIER_SCRIPT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SITES="${1:-${VIGIE_SITES:-$DOSSIER_SCRIPT/sites.txt}}"
LOG="${VIGIE_LOG:-${XDG_STATE_HOME:-$HOME/.local/state}/vigie/sondes.log}"
DELAI="${VIGIE_DELAI:-10}"
AGENT="vigie/0.1 (projet de formation DevOps)"

erreur() {
  echo "vigie: $*" >&2
  exit 2
}

[[ -r "$SITES" ]] || erreur "fichier des sites introuvable : $SITES"
[[ "$DELAI" =~ ^[1-9][0-9]*$ ]] || erreur "VIGIE_DELAI doit être un entier positif : $DELAI"
mkdir -p "$(dirname "$LOG")"

# Un verrou empêche deux sondes de tourner en même temps,
# par exemple si cron relance la sonde avant la fin de la précédente.
exec 9>"$LOG.verrou"
if ! flock -n 9; then
  echo "vigie: une autre sonde est déjà en cours, abandon" >&2
  exit 0
fi

# Teste une adresse, affiche une ligne de résultat.
# Renvoie 0 si le site répond (code 2xx ou 3xx), 1 sinon.
sonder() {
  local url=$1 mesure code secondes ms etat

  # En cas d'échec (DNS, connexion refusée, délai dépassé), curl renvoie
  # une erreur mais affiche quand même le code 000 et le temps écoulé.
  mesure=$(curl --silent --output /dev/null --location \
    --max-time "$DELAI" --user-agent "$AGENT" \
    --write-out '%{http_code} %{time_total}' "$url" </dev/null) || true

  code=${mesure%% *}
  secondes=${mesure##* }
  ms=$(awk -v s="$secondes" 'BEGIN { printf "%d", s * 1000 }')

  if [[ $code =~ ^[23][0-9][0-9]$ ]]; then
    etat=UP
  else
    etat=DOWN
  fi

  echo "$(date -Iseconds) $etat $code $ms $url"
  [[ $etat == UP ]]
}

pannes=0
while IFS= read -r ligne || [[ -n $ligne ]]; do
  # Tout ce qui suit un # est un commentaire ; on garde le premier mot.
  read -r url _ <<<"${ligne%%#*}" || true
  [[ -n ${url:-} ]] || continue

  if [[ ! $url =~ ^https?:// ]]; then
    echo "vigie: ligne ignorée (adresse http ou https attendue) : $url" >&2
    continue
  fi

  if ! sonder "$url" | tee -a "$LOG"; then
    pannes=$((pannes + 1))
  fi
done <"$SITES"

if ((pannes > 0)); then
  exit 1
fi
