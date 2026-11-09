"""Fonctions d'aide partagées par les tests de la base et de l'API."""

from datetime import datetime, timedelta

from vigie.sonde import Resultat


def resultat(
    url: str,
    etat: str = "UP",
    code: int | None = 200,
    il_y_a: timedelta = timedelta(minutes=1),
    nom: str | None = None,
    erreur: str | None = None,
) -> Resultat:
    """Fabrique un résultat de sonde daté dans le passé."""
    date = (datetime.now().astimezone() - il_y_a).isoformat(timespec="seconds")
    return Resultat(
        date=date,
        nom=nom or url,
        url=url,
        etat=etat,
        code=code,
        duree_ms=120,
        erreur=erreur,
    )
