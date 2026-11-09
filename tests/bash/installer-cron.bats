#!/usr/bin/env bats
# Tests du script d'installation cron, sans toucher à la vraie crontab :
# une fausse commande « crontab » lit et écrit un simple fichier.

setup() {
  INSTALLEUR="$BATS_TEST_DIRNAME/../../sonde/installer-cron.sh"
  export XDG_STATE_HOME="$BATS_TEST_TMPDIR/state"
  export FAUSSE_CRONTAB="$BATS_TEST_TMPDIR/crontab"

  FAUX_BIN="$BATS_TEST_TMPDIR/bin"
  mkdir -p "$FAUX_BIN"
  cat >"$FAUX_BIN/crontab" <<'EOF'
#!/bin/bash
if [[ ${1:-} == -l ]]; then
  if [[ -f $FAUSSE_CRONTAB ]]; then cat "$FAUSSE_CRONTAB"; else echo "no crontab" >&2; exit 1; fi
elif [[ ${1:-} == - ]]; then
  cat >"$FAUSSE_CRONTAB"
fi
EOF
  chmod +x "$FAUX_BIN/crontab"
  export PATH="$FAUX_BIN:$PATH"

  echo "0 3 * * * /usr/bin/true # tâche existante" >"$FAUSSE_CRONTAB"
}

@test "l'installation ajoute la tâche toutes les 5 minutes" {
  run "$INSTALLEUR"
  [ "$status" -eq 0 ]
  grep -Eq '^\*/5 \* \* \* \* .*/sonde/vigie\.sh .*# vigie-sonde$' "$FAUSSE_CRONTAB"
}

@test "relancer l'installation ne crée pas de doublon" {
  "$INSTALLEUR"
  "$INSTALLEUR"
  [ "$(grep -c 'vigie-sonde' "$FAUSSE_CRONTAB")" -eq 1 ]
}

@test "l'installation garde les autres tâches" {
  "$INSTALLEUR"
  grep -q 'tâche existante' "$FAUSSE_CRONTAB"
}

@test "l'installation fonctionne même sans crontab existante" {
  rm "$FAUSSE_CRONTAB"
  run "$INSTALLEUR"
  [ "$status" -eq 0 ]
  [ "$(wc -l <"$FAUSSE_CRONTAB")" -eq 1 ]
}

@test "--retirer enlève la tâche Vigie et seulement elle" {
  "$INSTALLEUR"
  run "$INSTALLEUR" --retirer
  [ "$status" -eq 0 ]
  ! grep -q 'vigie-sonde' "$FAUSSE_CRONTAB"
  grep -q 'tâche existante' "$FAUSSE_CRONTAB"
}
