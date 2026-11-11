"""Lecture et validation de la configuration de Vigie (fichier TOML)."""

import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

import httpx

DELAI_PAR_DEFAUT = 10.0
PARALLELES_PAR_DEFAUT = 10
ECHECS_AVANT_ALERTE_PAR_DEFAUT = 2
LONGUEUR_MAX_URL = 2000  # au-delà, beaucoup de serveurs refusent la requête


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
    except OSError as erreur:
        # Un dossier à la place du fichier, des droits insuffisants...
        raise ErreurConfiguration(
            f"fichier de configuration illisible : {chemin} ({erreur.strerror})"
        ) from None
    except UnicodeDecodeError:
        raise ErreurConfiguration(f"{chemin} n'est pas encodé en UTF-8") from None
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
        if not isinstance(url, str):
            raise ErreurConfiguration(
                f"site n°{numero} : adresse http ou https attendue, reçu {url!r}"
            )
        probleme = probleme_url(url)
        if probleme:
            apercu = url if len(url) <= 80 else url[:77] + "..."
            raise ErreurConfiguration(
                f"site n°{numero} : adresse http ou https valide attendue ({probleme}),"
                f" reçu {apercu!r}"
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


def probleme_url(url: str) -> str | None:
    """Dit pourquoi une adresse est inutilisable par la sonde, ou None si elle convient.

    Toute adresse acceptée ici doit pouvoir être envoyée au client HTTP sans faire
    planter la sonde : la vérification a lieu au chargement, pas en plein passage.
    """
    if len(url) > LONGUEUR_MAX_URL:
        return f"adresse trop longue : {len(url)} caractères, {LONGUEUR_MAX_URL} au plus"
    if any(caractere.isspace() or not caractere.isprintable() for caractere in url):
        return "elle contient un espace ou un caractère invisible"
    try:
        morceaux = urlsplit(url)
        morceaux.port  # noqa: B018 (lire le port lève ValueError s'il est invalide)
    except ValueError as erreur:
        return f"mal formée : {erreur}"
    if morceaux.scheme not in ("http", "https"):
        return "elle doit commencer par http:// ou https://"
    if not morceaux.hostname:
        return "nom d'hôte manquant"
    try:
        httpx.URL(url)
    except httpx.InvalidURL as erreur:  # pragma: no cover
        # Aucun cas connu au 10/11/2026 : les adresses qu'httpx refuse contiennent des
        # caractères invisibles, déjà écartés plus haut. Filet de sécurité si une future
        # version d'httpx devient plus stricte.
        return f"refusée par le client HTTP : {erreur}"
    return None


def _est_nombre(valeur: object) -> bool:
    # En Python, True et False sont aussi des entiers : on les refuse explicitement.
    return isinstance(valeur, int | float) and not isinstance(valeur, bool)


def _est_entier(valeur: object) -> bool:
    return isinstance(valeur, int) and not isinstance(valeur, bool)
