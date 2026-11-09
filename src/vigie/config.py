"""Lecture et validation de la configuration de Vigie (fichier TOML)."""

import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

DELAI_PAR_DEFAUT = 10.0
PARALLELES_PAR_DEFAUT = 10
ECHECS_AVANT_ALERTE_PAR_DEFAUT = 2


class ErreurConfiguration(Exception):
    """La configuration est absente ou invalide."""


@dataclass(frozen=True)
class Site:
    nom: str
    url: str


@dataclass(frozen=True)
class Configuration:
    sites: tuple[Site, ...]
    delai: float = DELAI_PAR_DEFAUT  # secondes accordées à chaque site
    paralleles: int = PARALLELES_PAR_DEFAUT  # sites testés en même temps
    # échecs consécutifs avant d'ouvrir un incident : évite d'alerter pour un raté isolé
    echecs_avant_alerte: int = ECHECS_AVANT_ALERTE_PAR_DEFAUT


def charger(chemin: Path) -> Configuration:
    """Lit un fichier TOML et renvoie une configuration validée."""
    try:
        with chemin.open("rb") as fichier:
            donnees = tomllib.load(fichier)
    except FileNotFoundError:
        raise ErreurConfiguration(f"fichier de configuration introuvable : {chemin}") from None
    except tomllib.TOMLDecodeError as erreur:
        raise ErreurConfiguration(f"{chemin} n'est pas un fichier TOML valide : {erreur}") from None
    return analyser(donnees)


def analyser(donnees: dict[str, Any]) -> Configuration:
    """Valide des données déjà lues. Lève ErreurConfiguration au premier problème."""
    sonde = donnees.get("sonde", {})
    if not isinstance(sonde, dict):
        raise ErreurConfiguration("la section [sonde] est mal formée")

    delai = sonde.get("delai", DELAI_PAR_DEFAUT)
    if not _est_nombre(delai) or delai <= 0:
        raise ErreurConfiguration(f"sonde.delai doit être un nombre positif, reçu {delai!r}")

    paralleles = sonde.get("paralleles", PARALLELES_PAR_DEFAUT)
    if not _est_entier(paralleles) or paralleles < 1:
        raise ErreurConfiguration(
            f"sonde.paralleles doit être un entier supérieur ou égal à 1, reçu {paralleles!r}"
        )

    alertes = donnees.get("alertes", {})
    if not isinstance(alertes, dict):
        raise ErreurConfiguration("la section [alertes] est mal formée")
    echecs = alertes.get("echecs_avant_alerte", ECHECS_AVANT_ALERTE_PAR_DEFAUT)
    if not _est_entier(echecs) or echecs < 1:
        raise ErreurConfiguration(
            f"alertes.echecs_avant_alerte doit être un entier d'au moins 1, reçu {echecs!r}"
        )

    sites_bruts = donnees.get("sites", [])
    if not isinstance(sites_bruts, list) or not sites_bruts:
        raise ErreurConfiguration("la configuration doit déclarer au moins un site [[sites]]")

    sites: list[Site] = []
    deja_vues: set[str] = set()
    for numero, brut in enumerate(sites_bruts, start=1):
        if not isinstance(brut, dict):
            raise ErreurConfiguration(f"site n°{numero} : bloc [[sites]] attendu")

        url = brut.get("url")
        if not isinstance(url, str) or not url_valide(url):
            raise ErreurConfiguration(
                f"site n°{numero} : adresse http ou https attendue, reçu {url!r}"
            )
        if url in deja_vues:
            raise ErreurConfiguration(f"site n°{numero} : adresse en double : {url}")
        deja_vues.add(url)

        nom = brut.get("nom", url)
        if not isinstance(nom, str) or not nom.strip():
            raise ErreurConfiguration(f"site n°{numero} : le nom doit être un texte non vide")

        sites.append(Site(nom=nom.strip(), url=url))

    return Configuration(
        sites=tuple(sites),
        delai=float(delai),
        paralleles=paralleles,
        echecs_avant_alerte=echecs,
    )


def url_valide(url: str) -> bool:
    morceaux = urlparse(url)
    return morceaux.scheme in ("http", "https") and bool(morceaux.netloc)


def _est_nombre(valeur: object) -> bool:
    # En Python, True et False sont aussi des entiers : on les refuse explicitement.
    return isinstance(valeur, int | float) and not isinstance(valeur, bool)


def _est_entier(valeur: object) -> bool:
    return isinstance(valeur, int) and not isinstance(valeur, bool)
