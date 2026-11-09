"""Ligne de commande de Vigie.

    vigie sonder [--config FICHIER] [--log FICHIER]

Codes de sortie : 0 si tous les sites répondent, 1 si au moins un est en panne,
2 en cas d'erreur d'utilisation (comme la version Bash).
"""

import argparse
import asyncio
import fcntl
import os
import sys
from pathlib import Path

from vigie import __version__
from vigie.config import ErreurConfiguration, charger
from vigie.journal import ajouter
from vigie.sonde import Resultat, sonder_tous

CONFIG_PAR_DEFAUT = "config/vigie.toml"


def log_par_defaut() -> Path:
    # Emplacement standard des données produites par un programme (norme XDG).
    base = os.environ.get("XDG_STATE_HOME") or Path.home() / ".local" / "state"
    return Path(base) / "vigie" / "sondes.jsonl"


def construire_analyseur() -> argparse.ArgumentParser:
    analyseur = argparse.ArgumentParser(prog="vigie", description="Surveillance de sites web.")
    analyseur.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    commandes = analyseur.add_subparsers(dest="commande", required=True)

    sonder = commandes.add_parser("sonder", help="tester une fois tous les sites configurés")
    sonder.add_argument(
        "--config",
        type=Path,
        default=Path(os.environ.get("VIGIE_CONFIG", CONFIG_PAR_DEFAUT)),
        help=f"fichier de configuration (défaut : $VIGIE_CONFIG ou {CONFIG_PAR_DEFAUT})",
    )
    sonder.add_argument(
        "--log",
        type=Path,
        default=Path(os.environ["VIGIE_LOG"]) if "VIGIE_LOG" in os.environ else log_par_defaut(),
        help="fichier des résultats (défaut : $VIGIE_LOG ou ~/.local/state/vigie/sondes.jsonl)",
    )
    return analyseur


def formater(resultat: Resultat) -> str:
    code = resultat.code if resultat.code is not None else "---"
    ligne = f"{resultat.etat:<4} {code:>3} {resultat.duree_ms:>6} ms"
    ligne += f"  {resultat.nom} ({resultat.url})"
    if resultat.erreur:
        ligne += f"  [{resultat.erreur}]"
    return ligne


def commande_sonder(config_chemin: Path, log: Path) -> int:
    try:
        config = charger(config_chemin)
    except ErreurConfiguration as erreur:
        print(f"vigie: {erreur}", file=sys.stderr)
        return 2

    log.parent.mkdir(parents=True, exist_ok=True)
    with open(log.with_name(log.name + ".verrou"), "w") as verrou:
        # Un verrou empêche deux sondes de tourner en même temps.
        try:
            fcntl.flock(verrou, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            print("vigie: une autre sonde est déjà en cours, abandon", file=sys.stderr)
            return 0
        resultats = asyncio.run(sonder_tous(config))
        ajouter(log, resultats)

    for resultat in resultats:
        print(formater(resultat))
    return 0 if all(resultat.en_ligne for resultat in resultats) else 1


def main(argv: list[str] | None = None) -> int:
    arguments = construire_analyseur().parse_args(argv)
    if arguments.commande == "sonder":
        return commande_sonder(arguments.config, arguments.log)
    return 2  # pragma: no cover (argparse refuse déjà les commandes inconnues)
