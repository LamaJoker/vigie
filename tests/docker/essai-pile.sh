#!/usr/bin/env bash
# Essai de bout en bout de la pile Docker, dans un projet jetable (« vigie-essai ») :
# construit l'image, démarre base + API + sonde, vérifie, puis supprime tout.
# Les conteneurs et les données de la vraie pile (projet « vigie ») ne sont pas touchés.

set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/../.."

PROJET=vigie-essai
export VIGIE_PORT=18080
# Mesures périmées au bout de 3 x 10 = 30 s. Assez large même si un site met ses 10 s
# de délai maximal à répondre (5 s laissait trop peu de marge : essai instable).
export VIGIE_INTERVALLE=10
export VIGIE_SANTE_INTERVALLE=3s  # contrôle de santé de la sonde rapide, pour l'essai
export VIGIE_SANTE_DEMARRAGE=5s
VIGIE_MOT_DE_PASSE_BASE=$(python3 -c 'import secrets; print(secrets.token_hex(16))')
export VIGIE_MOT_DE_PASSE_BASE
ADRESSE="http://127.0.0.1:$VIGIE_PORT"

compose() { docker compose --project-name "$PROJET" "$@"; }
etape() { printf '\n=== %s\n' "$*"; }
sante_de() { docker inspect --format '{{.State.Health.Status}}' "$(compose ps -q "$1")" 2>/dev/null; }
attendre_sante() { # attendre_sante SERVICE ETAT SECONDES
  local _
  for _ in $(seq "$3"); do
    [[ $(sante_de "$1") == "$2" ]] && return 0
    sleep 1
  done
  return 1
}
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

etape "La page de statut s'affiche, à l'heure de Paris"
avant=$(TZ=Europe/Paris date +%H:%M)
page=$(curl -fsS "$ADRESSE/") || echec "page de statut absente"
apres=$(TZ=Europe/Paris date +%H:%M)  # au cas où la minute change pendant la requête
grep -q "<title>Vigie" <<<"$page" || echec "page de statut absente"
grep -q "fuseau Europe/Paris" <<<"$page" || echec "la page ne dit pas son fuseau horaire"
grep -q -e "$avant" -e "$apres" <<<"$page" || echec "la page n'affiche pas l'heure de Paris ($avant)"
echo "fuseau annoncé, heure de Paris ($avant) affichée"

etape "La sonde est en bonne santé"
attendre_sante sonde healthy 40 || echec "la sonde n'est pas « healthy » (état : $(sante_de sonde))"
compose exec -T sonde vigie sante-sonde

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

etape "Les migrations ont tourné, et les relancer ne change rien"
compose logs migrations | grep -E "Migration appliquée|Base de données" || true
compose logs migrations | grep -q "Base de données à jour" || echec "les migrations n'ont pas tourné"
relance=$(compose run --rm --no-deps migrations 2>&1) || echec "relancer les migrations échoue : $relance"
grep -q "déjà à jour" <<<"$relance" || echec "la relance a modifié la base : $relance"
grep "déjà à jour" <<<"$relance"

etape "50 requêtes simultanées : l'API garde 5 connexions à la base au plus"
seq 50 | xargs -P 50 -I{} curl -fsS -o /dev/null "$ADRESSE/api/sites" || echec "des requêtes ont échoué"
connexions=$(compose exec -T base psql -U vigie -d vigie -tAc \
  "SELECT count(*) FROM pg_stat_activity WHERE application_name = 'vigie-api'")
echo "connexions ouvertes par l'API : $connexions"
[[ $connexions -ge 1 && $connexions -le 5 ]] || echec "$connexions connexions ouvertes par l'API"

etape "Une sonde qui n'enregistre plus rien devient « unhealthy »"
compose stop base >/dev/null 2>&1
attendre_sante sonde unhealthy 60 || echec "sonde toujours « $(sante_de sonde) » sans base"
echo "base arrêtée : sonde $(sante_de sonde)"
compose start base >/dev/null 2>&1
attendre_sante sonde healthy 60 || echec "la sonde ne redevient pas « healthy »"
echo "base revenue : sonde $(sante_de sonde)"

etape "Après le redémarrage de la base, l'API répond du premier coup"
# Les connexions gardées par le pool sont mortes avec l'ancienne base. Le pool doit les
# écarter et en ouvrir de nouvelles pendant la requête : une seule requête de chaque
# sorte, sans nouvel essai, doit réussir.
duree=$(curl -fsS -o /dev/null -w '%{time_total}' "$ADRESSE/api/sites") ||
  echec "/api/sites échoue après le redémarrage de la base"
echo "/api/sites : réponse en $duree s"
curl -fsS -o /dev/null "$ADRESSE/" || echec "la page échoue après le redémarrage de la base"
curl -fsS "$ADRESSE/sante" || echec "/sante échoue après le redémarrage de la base"
echo

etape "La sonde s'arrête proprement (SIGTERM)"
compose stop sonde >/dev/null 2>&1
compose logs sonde | grep -q "SIGTERM reçu" || echec "la sonde n'a pas reçu SIGTERM"
echo "ok"

etape "Sonde arrêtée : la page signale des mesures périmées"
perime=false
for _ in $(seq 60); do
  if curl -fsS "$ADRESSE/api/sites" | python3 -c 'import json, sys; sys.exit(0 if all(s["perime"] for s in json.load(sys.stdin)) else 1)'; then
    perime=true
    break
  fi
  sleep 1
done
[[ $perime == true ]] || echec "les mesures ne sont jamais dites périmées"
curl -fsS "$ADRESSE/" | grep -q "Mesures périmées" || echec "pas de bandeau « Mesures périmées »"
curl -fsS "$ADRESSE/" | grep -q "Tous les sites répondent" && echec "bandeau vert malgré des mesures périmées"
echo "bandeau « Mesures périmées » affiché, plus de bandeau vert"

etape "Taille de l'image"
docker image ls vigie:local --format '{{.Repository}}:{{.Tag}}  {{.Size}}'

printf '\nTOUT EST BON\n'
