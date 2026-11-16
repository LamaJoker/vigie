"""Tests du contrôle d'épinglage (lot 8.4) et de la construction depuis le verrou.

Tout ce que le projet télécharge pour se construire doit être désigné par une empreinte,
pas par une étiquette qu'on peut déplacer : actions GitHub, images Docker, dépendances
Python. Le contrôle est scripts/verifier_epinglage.py, lancé par « make lint » et la CI.
"""

import importlib.util
from pathlib import Path

import pytest

RACINE = Path(__file__).parents[2]
_spec = importlib.util.spec_from_file_location(
    "verifier_epinglage", RACINE / "scripts" / "verifier_epinglage.py"
)
epinglage = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(epinglage)

SHA = "1f2e3d4c5b6a79881f2e3d4c5b6a79881f2e3d4c"
EMPREINTE = "sha256:" + "ab" * 32


# --- Actions GitHub -------------------------------------------------------------------


def test_action_epinglee_par_sha_avec_sa_version():
    assert epinglage.problemes_workflow(f"      - uses: actions/checkout@{SHA}  # v5.0.0\n") == []


@pytest.mark.parametrize(
    ("ligne", "motif"),
    [
        ("- uses: actions/checkout@v5", "SHA"),
        ("- uses: actions/checkout@main", "SHA"),
        ("- uses: actions/checkout@1f2e3d4", "SHA"),  # SHA abrégé : ambigu
        (f"- uses: actions/checkout@{SHA}", "version"),  # sans la version en commentaire
        ("- uses: actions/checkout", "SHA"),
        ("- uses: docker://alpine:3.22", "empreinte"),
    ],
)
def test_action_mal_epinglee(ligne, motif):
    [probleme] = epinglage.problemes_workflow(ligne + "\n")
    assert motif in probleme
    assert "ligne 1" in probleme


def test_action_locale_acceptee():
    assert epinglage.problemes_workflow("  - uses: ./.github/actions/preparer\n") == []


def test_docker_dans_une_commande_de_workflow():
    texte = "        run: docker run --rm -i hadolint/hadolint:latest-debian < Dockerfile\n"
    [probleme] = epinglage.problemes_workflow(texte)
    assert "hadolint/hadolint:latest-debian" in probleme


# --- Dockerfile -----------------------------------------------------------------------


def test_dockerfile_epingle():
    texte = (
        f"FROM ghcr.io/astral-sh/uv:0.13.8@{EMPREINTE} AS uv\n"
        f"FROM python:3.14-slim@{EMPREINTE} AS construction\n"
        "COPY --from=uv /uv /usr/local/bin/uv\n"
        f"FROM python:3.14-slim@{EMPREINTE}\n"
        "COPY --from=construction /opt/vigie /opt/vigie\n"
        "COPY --from=0 /a /a\n"
    )
    assert epinglage.problemes_dockerfile(texte) == []


@pytest.mark.parametrize(
    "texte",
    [
        "FROM python:3.14-slim\n",
        "FROM python:3.14-slim AS construction\n",
        "FROM --platform=linux/amd64 python:3.14-slim\n",
        "ARG VERSION=3.14\nFROM python:${VERSION}-slim\n",
        "FROM scratch\nCOPY --from=ghcr.io/astral-sh/uv:0.13.8 /uv /uv\n",
        "# syntax=docker/dockerfile:1\nFROM scratch\n",
    ],
)
def test_dockerfile_mal_epingle(texte):
    assert len(epinglage.problemes_dockerfile(texte)) == 1


def test_dockerfile_scratch_accepte():
    assert epinglage.problemes_dockerfile("FROM scratch\n") == []


# --- compose.yaml et Makefile -------------------------------------------------------


def test_compose():
    texte = (
        f"  base:\n    image: postgres:18-alpine@{EMPREINTE}\n"
        "  api:\n    image: vigie:local  # construite ici\n"
        "  autre:\n    image: redis:8\n"
    )
    [probleme] = epinglage.problemes_compose(texte)
    assert "redis:8" in probleme
    assert "ligne 6" in probleme


def test_makefile():
    texte = (
        f"IMAGE_HADOLINT := hadolint/hadolint:v2.14.0-debian@{EMPREINTE}\n"
        "IMAGE_ACTIONLINT := rhysd/actionlint:latest\n"
        "lint:\n"
        "\tdocker run --rm -i $(IMAGE_HADOLINT) < Dockerfile\n"
        '\tdocker run --rm -v "$(CURDIR):/depot:ro" -w /depot koalaman/shellcheck:stable\n'
    )
    problemes = epinglage.problemes_commandes(texte)
    assert len(problemes) == 2
    assert "rhysd/actionlint:latest" in problemes[0]
    assert "koalaman/shellcheck:stable" in problemes[1]


# --- Le dépôt lui-même ------------------------------------------------------------


def test_le_depot_est_entierement_epingle():
    assert epinglage.verifier(RACINE) == []


def test_un_depot_sans_verrou_est_signale(tmp_path):
    (tmp_path / "Dockerfile").write_text(f"FROM python:3.14-slim@{EMPREINTE}\n")
    assert any("uv.lock" in probleme for probleme in epinglage.verifier(tmp_path))


def test_la_commande_signale_les_problemes(tmp_path, capsys):
    (tmp_path / "uv.lock").write_text("version = 1\n")
    (tmp_path / "Dockerfile").write_text("FROM python:3.14-slim\n")
    assert epinglage.main([str(tmp_path)]) == 1
    assert "python:3.14-slim" in capsys.readouterr().out


def test_la_commande_sur_le_depot(capsys):
    assert epinglage.main([str(RACINE)]) == 0
    assert "toutes épinglées" in capsys.readouterr().out


# --- La construction installe depuis le verrou ------------------------------------------


def test_le_dockerfile_installe_depuis_le_verrou():
    dockerfile = (RACINE / "Dockerfile").read_text(encoding="utf-8")
    assert "uv sync --locked" in dockerfile
    assert "pip install" not in dockerfile


def test_la_ci_installe_depuis_le_verrou():
    ci = (RACINE / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
    assert "uv sync --locked" in ci
    assert "uv lock --check" in ci  # le verrou correspond bien à pyproject.toml
    assert "pip install" not in ci


def test_le_paquet_se_construit_sans_rien_telecharger():
    # Le backend uv_build est intégré à uv : pas de setuptools téléchargé à la construction.
    pyproject = (RACINE / "pyproject.toml").read_text(encoding="utf-8")
    assert 'build-backend = "uv_build"' in pyproject
    assert "required-version" in pyproject  # tout le monde utilise la même version de uv
