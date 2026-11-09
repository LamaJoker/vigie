#!/usr/bin/env bash
# Essai de bout en bout de la pile Docker, dans un projet jetable (« vigie-essai ») :
# construit l'image, démarre base + API + sonde, vérifie, puis supprime tout.
# Les conteneurs et les données de la vraie pile (projet « vigie ») ne sont pas touchés.

set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/../.."

PROJET=vigie-essai
export VIGIE_PORT=18080
export VIGIE_INTERVALLE=5
VIGIE_MOT_DE_PASSE_BASE=$(python3 -c 'import secrets; print(secrets.token_hex(16))')
export VIGIE_MOT_DE_PASSE_BASE
ADRESSE="http://127.0.0.1:$VIGIE_PORT"

compose() { docker compose --project-name "$PROJET" "$@"; }
etape() { printf '\n=== %s\n' "$*"; }
echec() {
  echo "ÉCHEC : $*" >&2
  compose ps -a >&2 || true
  compose logs --tail=30 >&2 || true
  exit 1
}
nettoyer() { compose down --volumes --remove-orphans >/dev/null 2>&1 || true; }
trap nettoyer EXIT

etape "Construction et démarrage"
compose up --detach --build --quiet-pull 2>&1 | tail -5

etape "L'API répond et sa base aussi"
for _ in $(seq 60); do
  curl -fsS "$ADRESSE/sante" >/dev/null 2>&1 && break
  sleep 1
done
sante=$(curl -fsS "$ADRESSE/sante") || echec "/sante ne répond pas"
echo "$sante"
[[ $sante == *'"base":"ok"'* ]] || echec "la base n'est pas joignable"

etape "La sonde a enregistré des mesures"
mesures=0
for _ in $(seq 30); do
  mesures=$(curl -fsS "$ADRESSE/api/sites" |
    python3 -c 'import json, sys; print(sum(1 for site in json.load(sys.stdin) if site["etat"]))')
  [[ $mesures -gt 0 ]] && break
  sleep 2
done
[[ $mesures -gt 0 ]] || echec "aucune mesure enregistrée par la sonde"
echo "$mesures site(s) mesuré(s)"

etape "La page de statut s'affiche"
curl -fsS "$ADRESSE/" | grep -q "<title>Vigie" || echec "page de statut absente"
echo "ok"

etape "Les conteneurs ne tournent pas en root"
for service in api sonde; do
  uid=$(compose exec -T "$service" id -u)
  echo "$service : utilisateur $uid"
  [[ $uid != 0 ]] || echec "$service tourne en root"
done

etape "Le système de fichiers de l'image est en lecture seule"
if compose exec -T api touch /opt/vigie/essai 2>/dev/null; then
  echec "écriture possible dans l'image"
fi
echo "écriture refusée, comme prévu"

etape "La base n'est pas joignable depuis la machine"
port_base=$(compose port base 5432 2>/dev/null || true)
[[ -z $port_base || $port_base == ":0" ]] || echec "le port de la base est publié : $port_base"
echo "aucun port publié"

etape "La sonde s'arrête proprement (SIGTERM)"
compose stop sonde >/dev/null 2>&1
compose logs sonde | grep -q "SIGTERM reçu" || echec "la sonde n'a pas reçu SIGTERM"
echo "ok"

etape "Taille de l'image"
docker image ls vigie:local --format '{{.Repository}}:{{.Tag}}  {{.Size}}'

printf '\nTOUT EST BON\n'
