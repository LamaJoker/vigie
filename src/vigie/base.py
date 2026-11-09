"""Stockage des résultats dans PostgreSQL.

L'adresse de la base n'est jamais écrite dans le code ni dans la configuration :
elle vient de la variable d'environnement VIGIE_DATABASE_URL (ou de l'option --base),
parce qu'elle peut contenir un mot de passe.
"""

from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta
from importlib import resources
from typing import Any

import psycopg
from psycopg.rows import dict_row

from vigie.config import Site
from vigie.sonde import Resultat

PERIODE_DISPONIBILITE = timedelta(hours=24)


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


def connecter(url: str) -> psycopg.Connection[dict[str, Any]]:
    return psycopg.connect(url, row_factory=dict_row, connect_timeout=5)


def initialiser(conn: psycopg.Connection) -> None:
    """Crée les tables si elles n'existent pas encore."""
    schema = resources.files("vigie").joinpath("schema.sql").read_text(encoding="utf-8")
    conn.execute(schema)
    conn.commit()


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


def historique(conn: psycopg.Connection, url: str, limite: int = 50) -> list[dict[str, Any]]:
    """Derniers résultats d'un site, du plus récent au plus ancien."""
    return conn.execute(
        "SELECT date, etat, code, duree_ms, erreur FROM sondes"
        " WHERE url = %s ORDER BY date DESC, id DESC LIMIT %s",
        (url, limite),
    ).fetchall()
