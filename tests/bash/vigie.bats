#!/usr/bin/env bats
# Tests de la sonde Bash. Lancement : bats tests/

setup_file() {
  export PORT=$((20000 + RANDOM % 20000))
  # 3>&- : le serveur ne doit pas garder ouvert le canal interne de bats
  python3 "$BATS_TEST_DIRNAME/serveur_http.py" "$PORT" 2>/dev/null 3>&- &
  echo $! >"$BATS_FILE_TMPDIR/serveur.pid"

  # Attend que le serveur soit prêt (5 secondes au plus).
  for _ in $(seq 50); do
    curl -s -o /dev/null "http://127.0.0.1:$PORT/200" && return 0
    sleep 0.1
  done
  echo "le serveur de test n'a pas démarré" >&2
  return 1
}

teardown_file() {
  kill "$(cat "$BATS_FILE_TMPDIR/serveur.pid")" 2>/dev/null || true
}

setup() {
  export VIGIE_LOG="$BATS_TEST_TMPDIR/sondes.log"
  export VIGIE_DELAI=2
  SONDE="$BATS_TEST_DIRNAME/../../sonde/vigie.sh"
  SITES="$BATS_TEST_TMPDIR/sites.txt"
  BASE="http://127.0.0.1:$PORT"
}

@test "un site qui répond 200 est noté UP" {
  echo "$BASE/200" >"$SITES"
  run "$SONDE" "$SITES"
  [ "$status" -eq 0 ]
  grep -Eq "^[0-9T:+-]+ UP 200 [0-9]+ $BASE/200$" "$VIGIE_LOG"
}

@test "un site qui répond 503 est noté DOWN et la sonde sort en erreur" {
  echo "$BASE/503" >"$SITES"
  run "$SONDE" "$SITES"
  [ "$status" -eq 1 ]
  grep -q " DOWN 503 " "$VIGIE_LOG"
}

@test "un site injoignable est noté DOWN avec le code 000" {
  echo "http://127.0.0.1:1/" >"$SITES"
  run "$SONDE" "$SITES"
  [ "$status" -eq 1 ]
  grep -q " DOWN 000 " "$VIGIE_LOG"
}

@test "un site trop lent est abandonné au bout du délai" {
  echo "$BASE/lent" >"$SITES"
  VIGIE_DELAI=1 run "$SONDE" "$SITES"
  [ "$status" -eq 1 ]
  grep -q " DOWN 000 " "$VIGIE_LOG"
  # le temps mesuré reste proche du délai d'une seconde
  ms=$(awk '{ print $4 }' "$VIGIE_LOG")
  [ "$ms" -ge 900 ] && [ "$ms" -lt 2000 ]
}

@test "une seule panne parmi plusieurs sites suffit pour sortir en erreur" {
  printf '%s\n' "$BASE/200" "$BASE/503" "$BASE/204" >"$SITES"
  run "$SONDE" "$SITES"
  [ "$status" -eq 1 ]
  [ "$(grep -c ' UP ' "$VIGIE_LOG")" -eq 2 ]
  [ "$(grep -c ' DOWN ' "$VIGIE_LOG")" -eq 1 ]
}

@test "les commentaires et les lignes vides sont ignorés" {
  printf '# un commentaire\n\n   %s   # en fin de ligne\n\n' "$BASE/200" >"$SITES"
  run "$SONDE" "$SITES"
  [ "$status" -eq 0 ]
  [ "$(wc -l <"$VIGIE_LOG")" -eq 1 ]
}

@test "une dernière ligne sans retour à la ligne est quand même lue" {
  printf '%s' "$BASE/200" >"$SITES"
  run "$SONDE" "$SITES"
  [ "$status" -eq 0 ]
  [ "$(wc -l <"$VIGIE_LOG")" -eq 1 ]
}

@test "une ligne qui n'est pas une adresse web est signalée puis ignorée" {
  printf '%s\n' "pas-une-adresse" "$BASE/200" >"$SITES"
  run "$SONDE" "$SITES"
  [ "$status" -eq 0 ]
  [[ "$output" == *"ligne ignorée"* ]]
  [ "$(wc -l <"$VIGIE_LOG")" -eq 1 ]
}

@test "les résultats s'ajoutent au log sans l'écraser" {
  echo "$BASE/200" >"$SITES"
  "$SONDE" "$SITES"
  "$SONDE" "$SITES"
  [ "$(wc -l <"$VIGIE_LOG")" -eq 2 ]
}

@test "un fichier de sites absent donne une erreur claire" {
  run "$SONDE" "$BATS_TEST_TMPDIR/absent.txt"
  [ "$status" -eq 2 ]
  [[ "$output" == *"introuvable"* ]]
}

@test "un délai invalide est refusé" {
  echo "$BASE/200" >"$SITES"
  VIGIE_DELAI=zero run "$SONDE" "$SITES"
  [ "$status" -eq 2 ]
}

@test "deux sondes ne tournent jamais en même temps" {
  echo "$BASE/lent" >"$SITES"
  VIGIE_DELAI=3 "$SONDE" "$SITES" >/dev/null 3>&- &
  premiere=$!
  sleep 0.5
  run "$SONDE" "$SITES"
  wait "$premiere" || true
  [ "$status" -eq 0 ]
  [[ "$output" == *"déjà en cours"* ]]
  [ "$(wc -l <"$VIGIE_LOG")" -eq 1 ]
}
