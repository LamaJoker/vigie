"""Vérifie les liens relatifs des fichiers Markdown suivis par Git (fichiers et ancres).

Utilisation (dans le dépôt) : python3 verifier_liens.py
Code de sortie : 0 si tout est bon, 1 sinon (chaque lien cassé est listé).
Les liens http(s) ne sont pas vérifiés ici : ils pointent hors du dépôt.
"""

import re
import subprocess
import sys
import unicodedata
from pathlib import Path

LIEN = re.compile(r"!?\[[^\]]*\]\(([^)\s]+)(?:\s+\"[^\"]*\")?\)")
TITRE = re.compile(r"^#{1,6}\s+(.*)$", re.M)
BLOC_CODE = re.compile(r"^```.*?^```", re.M | re.S)


def ancre_github(titre: str) -> str:
    """Reproduit la façon dont GitHub transforme un titre en ancre."""
    titre = re.sub(r"[`*_]", "", titre.strip().lower())
    titre = "".join(c for c in titre if c.isalnum() or c in " -" or unicodedata.category(c) == "Mn")
    return titre.replace(" ", "-")


def ancres(fichier: Path) -> set[str]:
    texte = BLOC_CODE.sub("", fichier.read_text(encoding="utf-8"))
    return {ancre_github(t) for t in TITRE.findall(texte)}


fichiers = subprocess.run(
    ["git", "ls-files", "*.md"], capture_output=True, text=True, check=True
).stdout.split()

casses = []
verifies = 0
for nom in fichiers:
    fichier = Path(nom)
    texte = BLOC_CODE.sub("", fichier.read_text(encoding="utf-8"))
    for cible in LIEN.findall(texte):
        if re.match(r"^[a-z]+:", cible):  # http:, https:, mailto:
            continue
        verifies += 1
        chemin, _, ancre = cible.partition("#")
        destination = (fichier.parent / chemin).resolve() if chemin else fichier.resolve()
        if not destination.exists():
            casses.append(f"{nom} : {cible} (fichier introuvable)")
        elif ancre and destination.suffix == ".md" and ancre not in ancres(destination):
            casses.append(f"{nom} : {cible} (ancre introuvable)")

print(f"{len(fichiers)} fichiers Markdown, {verifies} liens relatifs vérifiés")
for casse in casses:
    print(f"CASSÉ  {casse}")
print("aucun lien cassé" if not casses else f"{len(casses)} lien(s) cassé(s)")
sys.exit(1 if casses else 0)
