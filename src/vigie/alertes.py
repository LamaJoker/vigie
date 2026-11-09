"""Incidents : une alerte quand un site tombe, une autre quand il revient, jamais plus.

Le principe :
- un site est déclaré en panne après N échecs consécutifs (N = echecs_avant_alerte),
  pour ne pas alerter sur un raté isolé ;
- la panne ouvre un incident ; la base garantit qu'un site n'a qu'un incident ouvert ;
- le retour du site ferme l'incident ;
- chaque incident porte deux cases « alerte envoyée » (début, fin). Une alerte qui n'a
  pas pu partir (Discord injoignable...) est retentée au passage suivant.
"""

from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

import psycopg

from vigie.sonde import Resultat

PANNE = "panne"
RETABLISSEMENT = "retablissement"


@dataclass(frozen=True)
class Alerte:
    incident: int
    type: str  # PANNE ou RETABLISSEMENT
    nom: str
    url: str
    debut: datetime
    fin: datetime | None
    cause: str | None

    @property
    def duree(self) -> timedelta | None:
        return self.fin - self.debut if self.fin else None

    def en_texte(self) -> str:
        if self.type == PANNE:
            return f"Alerte : {self.nom} est en panne ({self.cause or 'cause inconnue'})"
        return f"Alerte : {self.nom} est rétabli après {formater_duree(self.duree)}"


def formater_duree(duree: timedelta | None) -> str:
    if duree is None:
        return "en cours"
    secondes = max(0, int(duree.total_seconds()))
    heures, reste = divmod(secondes, 3600)
    minutes, secondes = divmod(reste, 60)
    morceaux = []
    if heures:
        morceaux.append(f"{heures} h")
    if minutes:
        morceaux.append(f"{minutes} min")
    if secondes or not morceaux:
        morceaux.append(f"{secondes} s")
    return " ".join(morceaux)


def cause_de(resultat: Resultat) -> str:
    return resultat.erreur or f"code HTTP {resultat.code}"


def mettre_a_jour_incidents(
    conn: psycopg.Connection, resultats: Iterable[Resultat], echecs_avant_alerte: int
) -> None:
    """Ouvre ou ferme les incidents d'après les résultats, déjà enregistrés en base."""
    for resultat in resultats:
        if resultat.en_ligne:
            conn.execute(
                "UPDATE incidents SET fin = %s WHERE url = %s AND fin IS NULL",
                (datetime.fromisoformat(resultat.date), resultat.url),
            )
            continue

        derniers = conn.execute(
            # id départage deux mesures enregistrées dans la même seconde
            "SELECT etat, date FROM sondes WHERE url = %s ORDER BY date DESC, id DESC LIMIT %s",
            (resultat.url, echecs_avant_alerte),
        ).fetchall()
        assez_d_echecs = len(derniers) == echecs_avant_alerte and all(
            ligne["etat"] == "DOWN" for ligne in derniers
        )
        if assez_d_echecs:
            # La panne commence au premier des échecs consécutifs.
            # ON CONFLICT : si un incident est déjà ouvert pour ce site, on ne fait rien.
            conn.execute(
                "INSERT INTO incidents (nom, url, debut, cause) VALUES (%s, %s, %s, %s)"
                " ON CONFLICT (url) WHERE fin IS NULL DO NOTHING",
                (resultat.nom, resultat.url, derniers[-1]["date"], cause_de(resultat)),
            )
    conn.commit()


def alertes_en_attente(conn: psycopg.Connection) -> list[Alerte]:
    """Alertes pas encore envoyées, de la plus ancienne à la plus récente."""
    lignes = conn.execute(
        "SELECT id, nom, url, debut, fin, cause, alerte_debut, alerte_fin FROM incidents"
        " WHERE NOT alerte_debut OR (fin IS NOT NULL AND NOT alerte_fin)"
        " ORDER BY debut, id"
    ).fetchall()
    alertes = []
    for ligne in lignes:
        commun = (ligne["id"],)
        details = (ligne["nom"], ligne["url"], ligne["debut"])
        if not ligne["alerte_debut"]:
            alertes.append(Alerte(*commun, PANNE, *details, None, ligne["cause"]))
        if ligne["fin"] is not None and not ligne["alerte_fin"]:
            alertes.append(Alerte(*commun, RETABLISSEMENT, *details, ligne["fin"], ligne["cause"]))
    return alertes


def marquer_envoyee(conn: psycopg.Connection, alerte: Alerte) -> None:
    if alerte.type == PANNE:
        conn.execute("UPDATE incidents SET alerte_debut = true WHERE id = %s", (alerte.incident,))
    else:
        conn.execute("UPDATE incidents SET alerte_fin = true WHERE id = %s", (alerte.incident,))
    conn.commit()


def incidents_recents(
    conn: psycopg.Connection, urls: Sequence[str], limite: int = 10
) -> list[dict[str, Any]]:
    """Derniers incidents des sites donnés, du plus récent au plus ancien.

    Seuls les sites encore surveillés comptent : un site retiré de la configuration
    ne doit pas laisser une panne « en cours » affichée pour toujours.
    """
    lignes = conn.execute(
        "SELECT nom, url, debut, fin, cause FROM incidents WHERE url = ANY(%s)"
        " ORDER BY debut DESC, id DESC LIMIT %s",
        (list(urls), limite),
    ).fetchall()
    for ligne in lignes:
        fin = ligne["fin"]
        ligne["en_cours"] = fin is None
        ligne["duree"] = formater_duree(fin - ligne["debut"] if fin else None)
    return lignes
