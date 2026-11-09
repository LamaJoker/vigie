#!/usr/bin/env bash
# Installe la tâche cron qui lance la sonde Vigie toutes les 5 minutes.
#
# Utilisation :
#   installer-cron.sh            installe ou met à jour la tâche
#   installer-cron.sh --retirer  supprime la tâche
#
# Le script peut être relancé sans risque : il remplace l'ancienne ligne
# Vigie au lieu d'en ajouter une deuxième (on dit qu'il est idempotent).

set -euo pipefail

DOSSIER_SCRIPT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SONDE="$DOSSIER_SCRIPT/vigie.sh"
ERREURS="${XDG_STATE_HOME:-$HOME/.local/state}/vigie/erreurs.log"
MARQUE="# vigie-sonde"

# minute heure jour mois jour-de-semaine commande
TACHE="*/5 * * * * $SONDE >/dev/null 2>>$ERREURS $MARQUE"

# Crontab actuelle, sans la ligne Vigie (vide s'il n'y en a pas encore).
crontab_sans_vigie() {
  crontab -l 2>/dev/null | grep -vF "$MARQUE" || true
}

# Le nouveau contenu est calculé entièrement AVANT d'être installé :
# lire et réécrire la crontab dans une même commande risquerait de la vider.
if [[ ${1:-} == --retirer ]]; then
  nouvelle=$(crontab_sans_vigie)
  if [[ -n $nouvelle ]]; then
    printf '%s\n' "$nouvelle" | crontab -
  else
    crontab -r 2>/dev/null || true
  fi
  echo "Tâche Vigie supprimée."
  exit 0
fi

mkdir -p "$(dirname "$ERREURS")"
nouvelle=$(
  crontab_sans_vigie
  echo "$TACHE"
)
printf '%s\n' "$nouvelle" | crontab -

echo "Tâche installée :"
crontab -l | grep -F "$MARQUE"
