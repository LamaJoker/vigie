"""Enregistrement des résultats, au format JSON Lines (un objet JSON par ligne).

Ce format se lit facilement avec des outils comme jq, et les outils de
centralisation des logs (Loki, étape 13) le comprennent directement.
"""

import json
from collections.abc import Iterable
from pathlib import Path

from vigie.sonde import Resultat


def ajouter(chemin: Path, resultats: Iterable[Resultat]) -> None:
    """Ajoute les résultats à la fin du fichier, sans jamais l'écraser."""
    chemin.parent.mkdir(parents=True, exist_ok=True)
    with chemin.open("a", encoding="utf-8") as fichier:
        for resultat in resultats:
            fichier.write(json.dumps(resultat.en_dict(), ensure_ascii=False) + "\n")
