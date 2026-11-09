"""Fonctions d'aide partagées par les tests de la base et de l'API."""

from datetime import datetime, timedelta

from vigie.sonde import Resultat

# Une seule heure de référence pour tous les tests : les durées calculées entre deux
# résultats sont exactes, au lieu de dépendre des quelques millisecondes écoulées.
MAINTENANT = datetime.now().astimezone().replace(microsecond=0)


def resultat(
    url: str,
    etat: str = "UP",
    code: int | None = 200,
    il_y_a: timedelta = timedelta(minutes=1),
    nom: str | None = None,
    erreur: str | None = None,
) -> Resultat:
    """Fabrique un résultat de sonde daté dans le passé."""
    return Resultat(
        date=(MAINTENANT - il_y_a).isoformat(timespec="seconds"),
        nom=nom or url,
        url=url,
        etat=etat,
        code=code,
        duree_ms=120,
        erreur=erreur,
    )
