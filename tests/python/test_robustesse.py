"""Lot 8.1 : une adresse mal écrite ou une erreur imprévue ne doit jamais arrêter la surveillance.

Les cas viennent de la revue du 10/11/2026, où ils ont été reproduits à la main.
"""

import asyncio
import time

import httpx
import pytest

from vigie.config import Configuration, ErreurConfiguration, Site, analyser, charger
from vigie.sonde import sonder_tous

ADRESSES_INVALIDES = {
    "port hors limites": "https://example.com:99999",
    "port non numérique": "https://example.com:abc/",
    "IPv6 non refermée": "http://[::1",
    "espace dans le nom": "https://exa mple.com",
    "tabulation": "https://exemple.test\t/chemin",
    "octet nul": "https://\x00.test",
    "sans nom d'hôte": "https://:443/",
    "adresse de 70 000 caractères": "https://exemple.test/" + "a" * 70_000,
}

ADRESSES_VALIDES = [
    "https://exemple.test:8443/chemin?q=1#ancre",
    "http://[::1]:8000/",
    "http://127.0.0.1:65535/",
    "https://xn--bcher-kva.example/",
]


def config_avec(*urls: str) -> dict:
    return {"sites": [{"url": url} for url in urls]}


# ------------------------------------------------------------- configuration


@pytest.mark.parametrize("url", ADRESSES_INVALIDES.values(), ids=ADRESSES_INVALIDES.keys())
def test_une_adresse_invalide_est_refusee_au_chargement(url):
    # Avant le lot 8.1 : soit acceptée puis plantage de tout le passage,
    # soit une trace Python (ValueError) au lieu d'un message.
    with pytest.raises(ErreurConfiguration, match="site n°2"):
        analyser(config_avec("https://example.com", url))


@pytest.mark.parametrize("url", ADRESSES_VALIDES)
def test_les_adresses_inhabituelles_mais_valides_sont_acceptees(url):
    assert analyser(config_avec(url)).sites[0].url == url


def test_le_message_ne_recopie_pas_une_adresse_geante():
    with pytest.raises(ErreurConfiguration) as erreur:
        analyser(config_avec(ADRESSES_INVALIDES["adresse de 70 000 caractères"]))
    assert len(str(erreur.value)) < 300


def test_un_fichier_qui_n_est_pas_en_utf8_est_refuse(tmp_path):
    fichier = tmp_path / "vigie.toml"
    fichier.write_bytes(b'[[sites]]\nurl = "https://exemple.test/caf\xe9"\n')
    with pytest.raises(ErreurConfiguration, match="UTF-8"):
        charger(fichier)


def test_un_dossier_a_la_place_du_fichier_est_refuse(tmp_path):
    with pytest.raises(ErreurConfiguration, match="illisible"):
        charger(tmp_path)


# --------------------------------------------------------------------- sonde


def lancer(gestionnaire, *urls: str) -> list:
    config = Configuration(sites=tuple(Site(url, url) for url in urls), delai=2)
    return asyncio.run(sonder_tous(config, transport=httpx.MockTransport(gestionnaire)))


@pytest.mark.parametrize(
    "erreur",
    [
        RuntimeError("bug imprévu"),
        ExceptionGroup("erreurs de connexion", [OverflowError("port must be 0-65535")]),
        UnicodeError("encodage impossible"),
    ],
    ids=["RuntimeError", "ExceptionGroup", "UnicodeError"],
)
def test_une_erreur_imprevue_sur_un_site_n_arrete_pas_les_autres(erreur):
    def gestionnaire(requete: httpx.Request) -> httpx.Response:
        if requete.url.host == "casse.test":
            raise erreur
        return httpx.Response(200)

    resultats = lancer(gestionnaire, "https://a.test", "https://casse.test", "https://b.test")

    assert [r.etat for r in resultats] == ["UP", "DOWN", "UP"]
    assert resultats[1].code is None
    assert resultats[1].erreur == f"erreur interne ({type(erreur).__name__})"


def test_l_erreur_imprevue_est_tracee(caplog):
    def gestionnaire(requete: httpx.Request) -> httpx.Response:
        raise RuntimeError("bug imprévu")

    lancer(gestionnaire, "https://casse.test")
    assert "https://casse.test" in caplog.text
    assert "RuntimeError" in caplog.text


def test_la_sonde_ne_telecharge_pas_le_corps_des_pages(serveur):
    # /gros annonce 50 Mo et les envoie au compte-gouttes : plus de 40 s pour tout lire.
    config = Configuration(sites=(Site("gros", f"{serveur}/gros"),), delai=5)
    debut = time.perf_counter()
    [resultat] = asyncio.run(sonder_tous(config))
    assert resultat.etat == "UP"
    assert resultat.code == 200
    assert time.perf_counter() - debut < 1
