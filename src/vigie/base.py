"""Stockage des résultats dans PostgreSQL.

L'adresse de la base n'est jamais écrite dans le code ni dans la configuration :
elle vient de la variable d'environnement VIGIE_DATABASE_URL (ou de l'option --base),
parce qu'elle peut contenir un mot de passe.

Le schéma (les tables) est créé et mis à jour par les migrations : voir migrateur.py.
"""

from collections.abc import Iterable, Sequence
from dataclasses import dataclass, replace
from datetime import UTC, datetime, timedelta
from typing import Any

import psycopg
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool

from vigie.config import Site
from vigie.sonde import Resultat

PERIODE_DISPONIBILITE = timedelta(hours=24)
# Nom des connexions de l'API, visible par l'exploitant dans pg_stat_activity.
NOM_CONNEXIONS_API = "vigie-api"
LOT_PURGE = 10_000  # mesures supprimées par transaction pendant une purge
# Une mesure est « périmée » quand elle a plus de 3 intervalles de sonde : la sonde a
# raté au moins deux passages de suite, elle ne tourne probablement plus.
INTERVALLES_AVANT_PEREMPTION = 3


@dataclass(frozen=True)
class EtatSite:
    """Dernier état connu d'un site et sa disponibilité récente."""

    nom: str
    url: str
    etat: str | None  # None tant qu'aucune mesure n'existe
    code: int | None
    duree_ms: int | None
    date: datetime | None
    erreur: str | None
    disponibilite: float | None  # part des mesures UP sur la période, de 0 à 1
    mesures: int  # nombre de mesures sur la période
    age_secondes: int | None = None  # âge de la dernière mesure
    perime: bool = False  # la dernière mesure est trop vieille pour être crue


def seuil_peremption(intervalle: float) -> timedelta:
    return timedelta(seconds=INTERVALLES_AVANT_PEREMPTION * intervalle)


def avec_fraicheur(
    etats: Iterable[EtatSite], intervalle: float, maintenant: datetime | None = None
) -> list[EtatSite]:
    """Ajoute à chaque état l'âge de sa dernière mesure, et s'il est périmé."""
    maintenant = maintenant or datetime.now(UTC)
    seuil = seuil_peremption(intervalle).total_seconds()
    resultat = []
    for etat in etats:
        if etat.date is None:
            resultat.append(etat)
            continue
        age = max(0, int((maintenant - etat.date).total_seconds()))
        resultat.append(replace(etat, age_secondes=age, perime=age > seuil))
    return resultat


def formater_age(secondes: float) -> str:
    """Âge lisible et arrondi : « 45 s », « 12 min », « 2 h 5 min », « 3 j 4 h »."""
    secondes = max(0, int(secondes))
    if secondes < 60:
        return f"{secondes} s"
    minutes = secondes // 60
    if minutes < 60:
        return f"{minutes} min"
    heures, minutes = divmod(minutes, 60)
    if heures < 24:
        return f"{heures} h {minutes} min" if minutes else f"{heures} h"
    jours, heures = divmod(heures, 24)
    return f"{jours} j {heures} h" if heures else f"{jours} j"


def connecter(url: str) -> psycopg.Connection[dict[str, Any]]:
    return psycopg.connect(url, row_factory=dict_row, connect_timeout=5)


def creer_pool(url: str, taille: int, attente: float) -> ConnectionPool:
    """Pool de connexions de l'API, fermé : l'application l'ouvre à son démarrage.

    Il garde au moins une connexion ouverte et au plus « taille ». Une requête qui ne
    trouve pas de connexion libre en « attente » secondes reçoit une erreur (503).
    """

    def verifier_avant_pret(conn: psycopg.Connection) -> None:
        """Vérifie une connexion avant de la prêter à une requête."""
        try:
            ConnectionPool.check_connection(conn)
        except psycopg.Error:
            # Une connexion morte en annonce d'autres : la base a sans doute redémarré.
            # On vérifie d'un coup toutes celles qui attendent dans le pool. Sinon, la
            # requête les essaierait une à une en patientant entre chaque (1 s, puis 2 s)
            # et finirait en 503 avant d'arriver aux connexions neuves.
            pool.check()
            raise

    pool = ConnectionPool(
        url,
        min_size=1,
        max_size=taille,
        timeout=attente,
        # Pendant une panne de la base, le pool réessaie de se connecter en espaçant ses
        # essais (1 s, 2 s, 4 s...). Par défaut il insiste 5 minutes : la base revenue,
        # l'API pouvait rester en erreur des minutes, jusqu'au prochain essai. Il
        # abandonne désormais au bout du temps d'attente d'une requête, et la requête
        # suivante relance aussitôt un essai.
        reconnect_timeout=attente,
        open=False,
        name=NOM_CONNEXIONS_API,
        kwargs={
            "row_factory": dict_row,
            "connect_timeout": 5,
            "application_name": NOM_CONNEXIONS_API,
        },
        # Après un redémarrage de la base, une connexion morte est remplacée au lieu de
        # faire échouer une requête.
        check=verifier_avant_pret,
    )
    return pool


def verifier(conn: psycopg.Connection) -> None:
    """Lève une erreur si la base ne répond pas."""
    conn.execute("SELECT 1")


def enregistrer(conn: psycopg.Connection, resultats: Iterable[Resultat]) -> int:
    """Ajoute des résultats de sonde. Renvoie le nombre de lignes ajoutées."""
    lignes = [
        (
            datetime.fromisoformat(r.date),
            r.nom,
            r.url,
            r.etat,
            r.code,
            r.duree_ms,
            r.erreur,
        )
        for r in resultats
    ]
    with conn.cursor() as curseur:
        # Requête paramétrée (%s) : les valeurs ne sont jamais collées dans le SQL,
        # ce qui protège contre les injections SQL.
        curseur.executemany(
            "INSERT INTO sondes (date, nom, url, etat, code, duree_ms, erreur)"
            " VALUES (%s, %s, %s, %s, %s, %s, %s)",
            lignes,
        )
    conn.commit()
    return len(lignes)


def etats(
    conn: psycopg.Connection,
    sites: Sequence[Site],
    periode: timedelta = PERIODE_DISPONIBILITE,
) -> list[EtatSite]:
    """Dernier résultat et disponibilité de chaque site, dans l'ordre donné."""
    urls = [site.url for site in sites]

    derniers = {
        ligne["url"]: ligne
        for ligne in conn.execute(
            "SELECT DISTINCT ON (url) url, date, etat, code, duree_ms, erreur"
            " FROM sondes WHERE url = ANY(%s)"
            " ORDER BY url, date DESC, id DESC",
            (urls,),
        )
    }
    statistiques = {
        ligne["url"]: ligne
        for ligne in conn.execute(
            "SELECT url, avg((etat = 'UP')::int)::float AS disponibilite, count(*) AS mesures"
            " FROM sondes WHERE url = ANY(%s) AND date >= now() - %s"
            " GROUP BY url",
            (urls, periode),
        )
    }

    resultat = []
    for site in sites:
        dernier = derniers.get(site.url, {})
        statistique = statistiques.get(site.url, {})
        resultat.append(
            EtatSite(
                nom=site.nom,
                url=site.url,
                etat=dernier.get("etat"),
                code=dernier.get("code"),
                duree_ms=dernier.get("duree_ms"),
                date=dernier.get("date"),
                erreur=dernier.get("erreur"),
                disponibilite=statistique.get("disponibilite"),
                mesures=statistique.get("mesures", 0),
            )
        )
    return resultat


def derniere_mesure(conn: psycopg.Connection, urls: Sequence[str]) -> datetime | None:
    """Date de la mesure la plus récente parmi ces sites, ou None s'il n'y en a aucune."""
    ligne = conn.execute(
        "SELECT max(date) AS date FROM sondes WHERE url = ANY(%s)", (list(urls),)
    ).fetchone()
    return ligne["date"] if ligne else None


def purger(conn: psycopg.Connection, jours: int, lot: int = LOT_PURGE) -> int:
    """Supprime les mesures de plus de « jours » jours. Renvoie le nombre supprimé.

    Les incidents sont gardés : ils sont peu nombreux et racontent l'historique du site.
    La suppression se fait par lots, chacun dans une transaction courte : une très longue
    transaction retarderait le nettoyage automatique de PostgreSQL (autovacuum).
    """
    total = 0
    while True:
        supprimees = conn.execute(
            "DELETE FROM sondes WHERE id IN ("
            " SELECT id FROM sondes WHERE date < now() - make_interval(days => %s) LIMIT %s)",
            (jours, lot),
        ).rowcount
        conn.commit()
        total += supprimees
        if supprimees < lot:
            return total


def historique(conn: psycopg.Connection, url: str, limite: int = 50) -> list[dict[str, Any]]:
    """Derniers résultats d'un site, du plus récent au plus ancien."""
    return conn.execute(
        "SELECT date, etat, code, duree_ms, erreur FROM sondes"
        " WHERE url = %s ORDER BY date DESC, id DESC LIMIT %s",
        (url, limite),
    ).fetchall()
