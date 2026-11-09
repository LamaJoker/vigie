"""Ligne de commande de Vigie.

    vigie sonder   [--config FICHIER] [--log FICHIER] [--base URL]
    vigie init-db  [--base URL]
    vigie serveur  [--config FICHIER] [--base URL] [--hote ADRESSE] [--port PORT]

Codes de sortie de « sonder » : 0 si tous les sites répondent, 1 si au moins un est
en panne, 2 en cas d'erreur (configuration, base de données injoignable...).
"""

import argparse
import asyncio
import fcntl
import os
import sys
from pathlib import Path

from vigie import __version__
from vigie.config import Configuration, ErreurConfiguration, charger
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

    option_config = argparse.ArgumentParser(add_help=False)
    option_config.add_argument(
        "--config",
        type=Path,
        default=Path(os.environ.get("VIGIE_CONFIG", CONFIG_PAR_DEFAUT)),
        help=f"fichier de configuration (défaut : $VIGIE_CONFIG ou {CONFIG_PAR_DEFAUT})",
    )
    option_base = argparse.ArgumentParser(add_help=False)
    option_base.add_argument(
        "--base",
        default=os.environ.get("VIGIE_DATABASE_URL"),
        help="adresse de la base PostgreSQL (défaut : $VIGIE_DATABASE_URL)",
    )

    sonder = commandes.add_parser(
        "sonder", parents=[option_config, option_base], help="tester une fois tous les sites"
    )
    sonder.add_argument(
        "--log",
        type=Path,
        default=Path(os.environ["VIGIE_LOG"]) if "VIGIE_LOG" in os.environ else log_par_defaut(),
        help="fichier des résultats (défaut : $VIGIE_LOG ou ~/.local/state/vigie/sondes.jsonl)",
    )

    commandes.add_parser(
        "init-db", parents=[option_base], help="créer les tables de la base de données"
    )

    serveur = commandes.add_parser(
        "serveur", parents=[option_config, option_base], help="lancer l'API et la page de statut"
    )
    serveur.add_argument(
        "--hote", default="127.0.0.1", help="adresse d'écoute (défaut : 127.0.0.1)"
    )
    serveur.add_argument("--port", type=int, default=8000, help="port d'écoute (défaut : 8000)")
    return analyseur


def erreur(message: str) -> int:
    print(f"vigie: {message}", file=sys.stderr)
    return 2


def lire_config(chemin: Path) -> Configuration | None:
    try:
        return charger(chemin)
    except ErreurConfiguration as probleme:
        erreur(str(probleme))
        return None


def formater(resultat: Resultat) -> str:
    code = resultat.code if resultat.code is not None else "---"
    ligne = f"{resultat.etat:<4} {code:>3} {resultat.duree_ms:>6} ms"
    ligne += f"  {resultat.nom} ({resultat.url})"
    if resultat.erreur:
        ligne += f"  [{resultat.erreur}]"
    return ligne


def enregistrer_en_base(url: str, resultats: list[Resultat]) -> bool:
    import psycopg

    from vigie import base

    try:
        with base.connecter(url) as conn:
            base.enregistrer(conn, resultats)
    except psycopg.Error as probleme:
        erreur(f"enregistrement en base impossible : {probleme}")
        return False
    return True


def commande_sonder(config_chemin: Path, log: Path, url_base: str | None) -> int:
    config = lire_config(config_chemin)
    if config is None:
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
        base_ok = url_base is None or enregistrer_en_base(url_base, resultats)

    for resultat in resultats:
        print(formater(resultat))
    if not base_ok:
        return 2
    return 0 if all(resultat.en_ligne for resultat in resultats) else 1


def commande_init_db(url_base: str | None) -> int:
    if not url_base:
        return erreur("adresse de la base manquante : --base ou VIGIE_DATABASE_URL")
    import psycopg

    from vigie import base

    try:
        with base.connecter(url_base) as conn:
            base.initialiser(conn)
    except psycopg.Error as probleme:
        return erreur(f"initialisation de la base impossible : {probleme}")
    print("Base de données prête.")
    return 0


def commande_serveur(config_chemin: Path, url_base: str | None, hote: str, port: int) -> int:
    if not url_base:
        return erreur("adresse de la base manquante : --base ou VIGIE_DATABASE_URL")
    config = lire_config(config_chemin)
    if config is None:
        return 2

    import uvicorn

    from vigie.api import creer_app

    uvicorn.run(creer_app(config, url_base), host=hote, port=port)
    return 0


def main(argv: list[str] | None = None) -> int:
    arguments = construire_analyseur().parse_args(argv)
    if arguments.commande == "sonder":
        return commande_sonder(arguments.config, arguments.log, arguments.base)
    if arguments.commande == "init-db":
        return commande_init_db(arguments.base)
    return commande_serveur(arguments.config, arguments.base, arguments.hote, arguments.port)
