"""Vérifie que tout ce que le projet télécharge pour se construire est désigné par une empreinte.

Une étiquette (« v5 », « 3.14-slim », « latest ») peut être déplacée vers un autre contenu,
par erreur ou par un attaquant. Une empreinte, non : elle désigne un contenu exact.

- actions GitHub : « uses: propriétaire/action@<SHA de commit complet>  # vX.Y.Z » ;
- images Docker : « nom:étiquette@sha256:<empreinte> », dans le Dockerfile (FROM, COPY
  --from, ligne syntax), compose.yaml (image:) et les commandes « docker run » du Makefile,
  des workflows et des scripts ;
- dépendances Python : uv.lock, qui donne l'empreinte de chaque paquet.

Usage : python scripts/verifier_epinglage.py [DOSSIER]   (code 1 si un problème est trouvé)
Voir docs/decisions/0007-tout-epingler-par-empreinte.md.
"""

import re
import sys
from pathlib import Path

EMPREINTE = re.compile(r"@sha256:[0-9a-f]{64}$")
SHA_COMMIT = re.compile(r"[0-9a-f]{40}")
VERSION_EN_COMMENTAIRE = re.compile(r"v?\d+(\.\d+)*")
# Images construites par le projet lui-même : rien à télécharger, donc rien à épingler.
IMAGES_CONSTRUITES = {"vigie:local"}

USES = re.compile(r"^\s*(?:-\s*)?uses:\s*([^\s#]+)\s*(?:#\s*(\S+))?")
FROM = re.compile(r"^\s*FROM\s+(?:--platform=\S+\s+)?(\S+)(?:\s+AS\s+(\S+))?", re.IGNORECASE)
COPIE_DEPUIS = re.compile(r"^\s*(?:COPY|ADD)\s+.*--from=(\S+)", re.IGNORECASE)
SYNTAXE = re.compile(r"^#\s*syntax\s*=\s*(\S+)", re.IGNORECASE)
IMAGE_COMPOSE = re.compile(r"^\s*image:\s*[\"']?([^\s\"'#]+)")
VARIABLE_IMAGE = re.compile(r"^\s*(IMAGE_\w+)\s*(?::=|\?=|=)\s*(\S+)")
# Un mot qui ressemble à une image : « nom:étiquette », « dépôt/nom », « nom@sha256:... ».
RESSEMBLE_A_UNE_IMAGE = re.compile(
    r"(?:[a-z0-9][a-z0-9._-]*(?::\d+)?/)*[a-z0-9][a-z0-9._-]*"
    r"(?::[A-Za-z0-9_][A-Za-z0-9_.-]*)?(?:@sha256:[0-9a-f]{64})?"
)


def _probleme(nom: str, numero: int, message: str) -> str:
    return f"{nom}, ligne {numero} : {message}"


def _image_sans_empreinte(image: str) -> bool:
    return not EMPREINTE.search(image)


def problemes_commandes(texte: str, nom: str = "Makefile") -> list[str]:
    """Images des commandes « docker run » et des variables IMAGE_... (Makefile, scripts)."""
    problemes = []
    for numero, ligne in enumerate(texte.splitlines(), start=1):
        variable = VARIABLE_IMAGE.match(ligne)
        if variable and _image_sans_empreinte(variable[2]):
            problemes.append(_probleme(nom, numero, f"image sans empreinte : {variable[2]}"))
        if "docker run" not in ligne:
            continue
        for mot in ligne.split():
            mot = mot.strip("\"'")
            if not any(signe in mot for signe in "/:@") or "$" in mot:
                continue
            if RESSEMBLE_A_UNE_IMAGE.fullmatch(mot) and _image_sans_empreinte(mot):
                problemes.append(_probleme(nom, numero, f"image sans empreinte : {mot}"))
    return problemes


def problemes_workflow(texte: str, nom: str = "workflow") -> list[str]:
    """Actions (uses:) d'un workflow GitHub, et ses commandes « docker run »."""
    problemes = []
    for numero, ligne in enumerate(texte.splitlines(), start=1):
        uses = USES.match(ligne)
        if not uses:
            continue
        action, commentaire = uses[1], uses[2]
        if action.startswith("./"):
            continue  # action du dépôt lui-même
        if action.startswith("docker://"):
            if _image_sans_empreinte(action):
                problemes.append(_probleme(nom, numero, f"image sans empreinte : {action}"))
            continue
        _, _, reference = action.partition("@")
        if not SHA_COMMIT.fullmatch(reference):
            problemes.append(
                _probleme(
                    nom, numero, f"action non épinglée par un SHA de commit complet : {action}"
                )
            )
        elif not (commentaire and VERSION_EN_COMMENTAIRE.fullmatch(commentaire)):
            problemes.append(
                _probleme(nom, numero, f"version manquante en commentaire (# vX.Y.Z) : {action}")
            )
    return problemes + problemes_commandes(texte, nom)


def problemes_dockerfile(texte: str, nom: str = "Dockerfile") -> list[str]:
    """Images de base (FROM), images copiées (COPY --from) et ligne « syntax »."""
    problemes = []
    etapes: set[str] = set()
    for numero, ligne in enumerate(texte.splitlines(), start=1):
        syntaxe = SYNTAXE.match(ligne)
        if syntaxe and _image_sans_empreinte(syntaxe[1]):
            problemes.append(_probleme(nom, numero, f"syntaxe sans empreinte : {syntaxe[1]}"))
            continue
        depart = FROM.match(ligne)
        if depart:
            image, etape = depart[1], depart[2]
            if "$" in image:
                problemes.append(
                    _probleme(nom, numero, f"image désignée par une variable : {image}")
                )
            elif (
                image != "scratch" and image.lower() not in etapes and _image_sans_empreinte(image)
            ):
                problemes.append(_probleme(nom, numero, f"image sans empreinte : {image}"))
            if etape:
                etapes.add(etape.lower())
            continue
        copie = COPIE_DEPUIS.match(ligne)
        if copie:
            source = copie[1]
            if source.lower() in etapes or source.isdigit():
                continue
            if "$" in source or _image_sans_empreinte(source):
                problemes.append(_probleme(nom, numero, f"image sans empreinte : {source}"))
    return problemes


def problemes_compose(texte: str, nom: str = "compose.yaml") -> list[str]:
    """Images des services d'un fichier Compose (sauf celles construites par le projet)."""
    problemes = []
    for numero, ligne in enumerate(texte.splitlines(), start=1):
        image = IMAGE_COMPOSE.match(ligne)
        if image and image[1] not in IMAGES_CONSTRUITES and _image_sans_empreinte(image[1]):
            problemes.append(_probleme(nom, numero, f"image sans empreinte : {image[1]}"))
    return problemes


def verifier(racine: Path) -> list[str]:
    """Tous les problèmes d'épinglage du dépôt situé dans « racine »."""
    problemes = []
    if not (racine / "uv.lock").is_file():
        problemes.append("uv.lock absent : les dépendances Python ne sont pas verrouillées")

    def lire(chemin: Path) -> tuple[str, str]:
        return chemin.read_text(encoding="utf-8"), str(chemin.relative_to(racine))

    if (racine / "Dockerfile").is_file():
        problemes += problemes_dockerfile(*lire(racine / "Dockerfile"))
    if (racine / "compose.yaml").is_file():
        problemes += problemes_compose(*lire(racine / "compose.yaml"))
    if (racine / "Makefile").is_file():
        problemes += problemes_commandes(*lire(racine / "Makefile"))
    for workflow in sorted((racine / ".github" / "workflows").glob("*.y*ml")):
        problemes += problemes_workflow(*lire(workflow))
    for script in sorted([*racine.glob("scripts/*.sh"), *racine.glob("tests/docker/*.sh")]):
        problemes += problemes_commandes(*lire(script))
    return problemes


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    racine = Path(argv[0]) if argv else Path(__file__).resolve().parents[1]
    problemes = verifier(racine)
    for probleme in problemes:
        print(probleme)
    if problemes:
        print(f"{len(problemes)} problème(s) d'épinglage")
        return 1
    print("Épinglage vérifié : actions, images et dépendances, toutes épinglées")
    return 0


if __name__ == "__main__":
    sys.exit(main())
