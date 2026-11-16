"""Ligne de commande de Vigie.

    vigie sonder         [--config FICHIER] [--log FICHIER] [--base URL]
    vigie surveiller     [mêmes options] [--intervalle SECONDES] [--passages N]
    vigie sante-sonde    [--config FICHIER] [--base URL]
    vigie migrer         [--base URL]          (ancien nom, toujours accepté : init-db)
    vigie purger         [--config FICHIER] [--base URL]
    vigie serveur        [--config FICHIER] [--base URL] [--hote ADRESSE] [--port PORT]
    vigie tester-alerte

Codes de sortie de « sonder » : 0 si tous les sites répondent, 1 si au moins un est
en panne, 2 en cas d'erreur (configuration, base de données injoignable...).

Les alertes ont besoin de la base (c'est elle qui se souvient des incidents en cours).
Elles partent sur Discord si VIGIE_DISCORD_WEBHOOK est définie, sinon elles sont
seulement affichées.
"""

import argparse
import asyncio
import fcntl
import os
import signal
import sys
import traceback
from datetime import UTC, datetime
from pathlib import Path
from threading import Event
from time import monotonic

from vigie import __version__
from vigie.config import Configuration, ErreurConfiguration, charger
from vigie.journal import ajouter
from vigie.sonde import Resultat, sonder_tous

CONFIG_PAR_DEFAUT = "config/vigie.toml"
VARIABLE_WEBHOOK = "VIGIE_DISCORD_WEBHOOK"
ERREURS_IMPREVUES_MAX = 5  # erreurs imprévues de suite avant que « surveiller » s'arrête
PERIODE_PURGE = 24 * 3600  # secondes entre deux purges des vieilles mesures par « surveiller »


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

    option_log = argparse.ArgumentParser(add_help=False)
    option_log.add_argument(
        "--log",
        type=Path,
        default=Path(os.environ["VIGIE_LOG"]) if "VIGIE_LOG" in os.environ else log_par_defaut(),
        help="fichier des résultats (défaut : $VIGIE_LOG ou ~/.local/state/vigie/sondes.jsonl)",
    )

    commandes.add_parser(
        "sonder",
        parents=[option_config, option_base, option_log],
        help="tester une fois tous les sites",
    )

    surveiller = commandes.add_parser(
        "surveiller",
        parents=[option_config, option_base, option_log],
        help="tester les sites en boucle, à intervalle régulier (pour un conteneur)",
    )
    surveiller.add_argument(
        "--intervalle",
        type=float,
        default=None,
        help="secondes entre deux passages"
        " (défaut : $VIGIE_INTERVALLE, sinon sonde.intervalle de la configuration)",
    )
    surveiller.add_argument(
        "--passages",
        type=int,
        default=0,
        help="nombre de passages avant l'arrêt (défaut : 0, sans fin)",
    )

    commandes.add_parser(
        "sante-sonde",
        parents=[option_config, option_base],
        help="code 0 si une mesure récente est en base (contrôle de santé de la sonde)",
    )

    commandes.add_parser(
        "migrer",
        aliases=["init-db"],
        parents=[option_base],
        help="créer ou mettre à jour les tables de la base (migrations)",
    )

    commandes.add_parser(
        "purger",
        parents=[option_config, option_base],
        help="supprimer les mesures plus vieilles que retention.jours (surveiller le fait"
        " une fois par jour)",
    )

    serveur = commandes.add_parser(
        "serveur", parents=[option_config, option_base], help="lancer l'API et la page de statut"
    )
    serveur.add_argument(
        "--hote", default="127.0.0.1", help="adresse d'écoute (défaut : 127.0.0.1)"
    )
    serveur.add_argument("--port", type=int, default=8000, help="port d'écoute (défaut : 8000)")

    commandes.add_parser(
        "tester-alerte", help=f"envoyer une alerte d'essai sur Discord (${VARIABLE_WEBHOOK})"
    )
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


def notifier(conn, alertes_a_envoyer) -> None:
    """Envoie les alertes en attente et note celles qui sont parties."""
    from vigie import alertes, notification

    for alerte in alertes_a_envoyer:
        print(alerte.en_texte())

    webhook = os.environ.get(VARIABLE_WEBHOOK)
    if not webhook:
        erreur(f"{VARIABLE_WEBHOOK} n'est pas définie : alertes affichées ici seulement")
        envoyees = list(alertes_a_envoyer)
    else:
        envoyees, problemes = notification.envoyer_discord(webhook, alertes_a_envoyer)
        for probleme in problemes:
            erreur(f"alerte non envoyée, nouvel essai au prochain passage : {probleme}")

    for alerte in envoyees:
        alertes.marquer_envoyee(conn, alerte)


def traiter_en_base(url: str, config: Configuration, resultats: list[Resultat]) -> bool:
    """Enregistre les résultats, met à jour les incidents et envoie les alertes."""
    import psycopg

    from vigie import alertes, base

    try:
        with base.connecter(url) as conn:
            base.enregistrer(conn, resultats)
            alertes.mettre_a_jour_incidents(conn, resultats, config.echecs_avant_alerte)
            alertes.fermer_incidents_retires(conn, [site.url for site in config.sites])
            en_attente = alertes.alertes_en_attente(conn)
            if en_attente:
                notifier(conn, en_attente)
    except psycopg.Error as probleme:
        erreur(f"enregistrement en base impossible : {probleme}")
        return False
    return True


def commande_sonder(config_chemin: Path, log: Path, url_base: str | None) -> int:
    config = lire_config(config_chemin)
    if config is None:
        return 2

    chemin_verrou = log.with_name(log.name + ".verrou")
    try:
        log.parent.mkdir(parents=True, exist_ok=True)
        chemin_verrou.touch()
    except OSError as probleme:
        # Message clair au lieu d'un plantage (cas trouvé par l'essai Docker).
        return erreur(f"journal inaccessible : {probleme}")

    with open(chemin_verrou, "w") as verrou:
        # Un verrou empêche deux sondes de tourner en même temps.
        try:
            fcntl.flock(verrou, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            print("vigie: une autre sonde est déjà en cours, abandon", file=sys.stderr)
            return 0
        resultats = asyncio.run(sonder_tous(config))
        try:
            ajouter(log, resultats)
        except OSError as probleme:
            erreur(f"écriture du journal impossible : {probleme}")
        for resultat in resultats:
            print(formater(resultat))
        base_ok = url_base is None or traiter_en_base(url_base, config, resultats)

    if not base_ok:
        return 2
    return 0 if all(resultat.en_ligne for resultat in resultats) else 1


def commande_surveiller(
    config_chemin: Path, log: Path, url_base: str | None, intervalle: float | None, passages: int
) -> int:
    """Lance « sonder » en boucle, jusqu'à un signal d'arrêt (SIGTERM, Ctrl+C).

    Docker arrête un conteneur en lui envoyant SIGTERM : on termine proprement le
    passage en cours au lieu d'être coupé au milieu d'une écriture en base.
    """
    if (intervalle is not None and intervalle < 0) or passages < 0:
        return erreur("--intervalle et --passages ne peuvent pas être négatifs")
    # Une configuration invalide est une erreur définitive : inutile de boucler.
    config = lire_config(config_chemin)
    if config is None:
        return 2
    # Priorité : option --intervalle, puis VIGIE_INTERVALLE, puis le fichier (voir charger).
    if intervalle is None:
        intervalle = config.intervalle

    arret = Event()

    def demander_arret(numero: int, _cadre: object) -> None:
        nom = signal.Signals(numero).name
        print(f"vigie: {nom} reçu, arrêt après le passage en cours", file=sys.stderr, flush=True)
        arret.set()

    anciens = {sig: signal.signal(sig, demander_arret) for sig in (signal.SIGTERM, signal.SIGINT)}
    try:
        numero = 0
        imprevues_de_suite = 0
        derniere_purge: float | None = None
        while not arret.is_set():
            numero += 1
            heure = datetime.now().astimezone().strftime("%H:%M:%S")
            print(f"--- passage {numero} à {heure}", flush=True)
            # Une erreur prévue (base injoignable...) n'arrête pas la boucle : elle peut se
            # résoudre. Une erreur imprévue non plus, sauf si elle se répète : on s'arrête
            # alors en erreur, pour que l'orchestrateur (Docker, Kubernetes) relance la sonde.
            try:
                code = commande_sonder(config_chemin, log, url_base)
                # Code 2 : la base vient d'être injoignable, c'est déjà signalé. La purge
                # attendra un passage où elle répond.
                if url_base and code != 2:
                    derniere_purge = purge_quotidienne(
                        url_base, config.retention_jours, derniere_purge
                    )
                imprevues_de_suite = 0
            except Exception:
                imprevues_de_suite += 1
                print(
                    f"vigie: erreur imprévue pendant le passage {numero}"
                    f" ({imprevues_de_suite}/{ERREURS_IMPREVUES_MAX} de suite)",
                    file=sys.stderr,
                )
                traceback.print_exc()
                if imprevues_de_suite >= ERREURS_IMPREVUES_MAX:
                    erreur("trop d'erreurs imprévues de suite, arrêt pour être relancé")
                    return 1
            sys.stdout.flush()
            if passages and numero >= passages:
                break
            arret.wait(intervalle)
    finally:
        for sig, ancien in anciens.items():
            signal.signal(sig, ancien)
    return 0


def commande_sante_sonde(config_chemin: Path, url_base: str | None) -> int:
    """Contrôle de santé de la sonde : une mesure récente existe-t-elle en base ?

    Code 0 : oui. Code 1 : aucune mesure, mesure trop vieille, ou base injoignable,
    c'est-à-dire que la sonde ne fait plus son travail. Code 2 : erreur d'utilisation.
    """
    if not url_base:
        return erreur("adresse de la base manquante : --base ou VIGIE_DATABASE_URL")
    config = lire_config(config_chemin)
    if config is None:
        return 2

    import psycopg

    from vigie import base

    try:
        with base.connecter(url_base) as conn:
            derniere = base.derniere_mesure(conn, [site.url for site in config.sites])
    except psycopg.Error as probleme:
        print(f"vigie: base injoignable : {probleme}", file=sys.stderr)
        return 1
    if derniere is None:
        print("vigie: aucune mesure enregistrée pour les sites surveillés", file=sys.stderr)
        return 1

    age = (datetime.now(UTC) - derniere).total_seconds()
    seuil = base.seuil_peremption(config.intervalle).total_seconds()
    if age > seuil:
        print(
            f"vigie: dernière mesure trop vieille : il y a {base.formater_age(age)}"
            f" (au plus {base.formater_age(seuil)})",
            file=sys.stderr,
        )
        return 1
    print(f"Sonde en bonne santé : dernière mesure il y a {base.formater_age(age)}.")
    return 0


def purge_quotidienne(url_base: str, jours: int, derniere: float | None) -> float | None:
    """Purge les vieilles mesures si la dernière purge réussie date d'au moins un jour.

    Renvoie le moment de la dernière purge réussie. L'horloge « monotone » ne recule
    jamais, même si l'heure du système change : un jour mesuré avec elle dure vraiment un jour.
    """
    maintenant = monotonic()
    if derniere is not None and maintenant - derniere < PERIODE_PURGE:
        return derniere
    if purger_en_base(url_base, jours) is None:
        return derniere  # échec : nouvel essai au prochain passage
    return maintenant


def purger_en_base(url_base: str, jours: int) -> int | None:
    """Supprime les mesures trop vieilles. Renvoie leur nombre, ou None en cas d'échec."""
    import psycopg

    from vigie import base

    try:
        with base.connecter(url_base) as conn:
            supprimees = base.purger(conn, jours)
    except psycopg.Error as probleme:
        erreur(f"purge des anciennes mesures impossible : {probleme}")
        return None
    pluriel = "s" if supprimees > 1 else ""
    print(f"Purge des mesures de plus de {jours} jours : {supprimees} supprimée{pluriel}.")
    return supprimees


def commande_purger(config_chemin: Path, url_base: str | None) -> int:
    if not url_base:
        return erreur("adresse de la base manquante : --base ou VIGIE_DATABASE_URL")
    config = lire_config(config_chemin)
    if config is None:
        return 2
    return 0 if purger_en_base(url_base, config.retention_jours) is not None else 2


def commande_migrer(url_base: str | None) -> int:
    """Crée ou met à jour les tables. Plusieurs lancements simultanés sont sans risque."""
    if not url_base:
        return erreur("adresse de la base manquante : --base ou VIGIE_DATABASE_URL")
    import psycopg

    from vigie import base, migrateur

    try:
        with base.connecter(url_base) as conn:
            bilan = migrateur.migrer(conn)
    except (migrateur.ErreurMigration, psycopg.Error) as probleme:
        return erreur(f"migration impossible : {probleme}")

    for migration in bilan.appliquees:
        print(f"Migration appliquée : {migration.nom}")
    if bilan.inconnues:
        # Cas d'un retour à une version précédente de Vigie : ce n'est pas bloquant tant
        # que les migrations restent compatibles avec le code d'avant (voir la décision 0006).
        versions = ", ".join(str(version) for version in bilan.inconnues)
        print(
            f"vigie: attention, migration(s) inconnue(s) de cette version de Vigie : {versions}."
            " La base a été mise à jour par une version plus récente.",
            file=sys.stderr,
        )
    etat = "à jour" if bilan.appliquees else "déjà à jour"
    print(f"Base de données {etat} (version {bilan.version}).")
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


def commande_tester_alerte() -> int:
    webhook = os.environ.get(VARIABLE_WEBHOOK)
    if not webhook:
        return erreur(f"{VARIABLE_WEBHOOK} n'est pas définie (voir .env.exemple)")

    from vigie import notification
    from vigie.alertes import PANNE, Alerte

    essai = Alerte(
        incident=0,
        type=PANNE,
        nom="Essai de Vigie",
        url="https://github.com/LamaJoker/vigie",
        debut=datetime.now().astimezone(),
        fin=None,
        cause="message d'essai : la configuration des alertes fonctionne",
    )
    _, problemes = notification.envoyer_discord(webhook, [essai])
    if problemes:
        return erreur(problemes[0])
    print("Alerte d'essai envoyée sur Discord.")
    return 0


def main(argv: list[str] | None = None) -> int:
    arguments = construire_analyseur().parse_args(argv)
    if arguments.commande == "sonder":
        return commande_sonder(arguments.config, arguments.log, arguments.base)
    if arguments.commande == "sante-sonde":
        return commande_sante_sonde(arguments.config, arguments.base)
    if arguments.commande == "surveiller":
        return commande_surveiller(
            arguments.config,
            arguments.log,
            arguments.base,
            arguments.intervalle,
            arguments.passages,
        )
    if arguments.commande in ("migrer", "init-db"):
        return commande_migrer(arguments.base)
    if arguments.commande == "purger":
        return commande_purger(arguments.config, arguments.base)
    if arguments.commande == "tester-alerte":
        return commande_tester_alerte()
    return commande_serveur(arguments.config, arguments.base, arguments.hote, arguments.port)
