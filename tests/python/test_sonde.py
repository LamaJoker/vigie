"""Tests de la sonde avec un faux réseau (httpx.MockTransport) : rapides et sans Internet."""

import asyncio
import time
from datetime import datetime

import httpx

from vigie.config import Configuration, Site
from vigie.sonde import AGENT, sonder_tous


def config_pour(*urls: str, delai: float = 2, paralleles: int = 10) -> Configuration:
    sites = tuple(Site(nom=f"site {numero}", url=url) for numero, url in enumerate(urls, 1))
    return Configuration(sites=sites, delai=delai, paralleles=paralleles)


def lancer(config: Configuration, gestionnaire) -> list:
    return asyncio.run(sonder_tous(config, transport=httpx.MockTransport(gestionnaire)))


def test_un_site_qui_repond_200_est_up():
    [resultat] = lancer(config_pour("https://a.test"), lambda requete: httpx.Response(200))
    assert resultat.etat == "UP"
    assert resultat.code == 200
    assert resultat.erreur is None
    assert resultat.en_ligne


def test_un_site_qui_repond_503_est_down():
    [resultat] = lancer(config_pour("https://a.test"), lambda requete: httpx.Response(503))
    assert resultat.etat == "DOWN"
    assert resultat.code == 503
    assert not resultat.en_ligne


def test_les_redirections_sont_suivies():
    def gestionnaire(requete: httpx.Request) -> httpx.Response:
        if requete.url.path == "/ancien":
            return httpx.Response(301, headers={"Location": "https://a.test/nouveau"})
        return httpx.Response(200)

    [resultat] = lancer(config_pour("https://a.test/ancien"), gestionnaire)
    assert resultat.etat == "UP"
    assert resultat.code == 200


def test_un_site_injoignable_est_down_sans_code():
    def gestionnaire(requete: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("connexion refusée", request=requete)

    [resultat] = lancer(config_pour("https://a.test"), gestionnaire)
    assert resultat.etat == "DOWN"
    assert resultat.code is None
    assert "connexion refusée" in resultat.erreur


def test_un_site_trop_lent_est_abandonne_au_bout_du_delai():
    async def gestionnaire(requete: httpx.Request) -> httpx.Response:
        await asyncio.sleep(5)
        return httpx.Response(200)

    [resultat] = lancer(config_pour("https://a.test", delai=0.2), gestionnaire)
    assert resultat.etat == "DOWN"
    assert resultat.code is None
    assert "pas de réponse en 0.2 s" in resultat.erreur
    assert 150 <= resultat.duree_ms < 1000


def test_les_sites_sont_testes_en_parallele():
    async def gestionnaire(requete: httpx.Request) -> httpx.Response:
        await asyncio.sleep(0.3)
        return httpx.Response(200)

    urls = [f"https://site{numero}.test" for numero in range(5)]
    debut = time.perf_counter()
    lancer(config_pour(*urls, paralleles=5), gestionnaire)
    # À la suite, 5 sites de 0,3 s prendraient 1,5 s.
    assert time.perf_counter() - debut < 1.0


def test_le_nombre_de_tests_simultanes_est_limite():
    en_cours = 0
    maximum = 0

    async def gestionnaire(requete: httpx.Request) -> httpx.Response:
        nonlocal en_cours, maximum
        en_cours += 1
        maximum = max(maximum, en_cours)
        await asyncio.sleep(0.05)
        en_cours -= 1
        return httpx.Response(200)

    urls = [f"https://site{numero}.test" for numero in range(8)]
    lancer(config_pour(*urls, paralleles=2), gestionnaire)
    assert maximum == 2


def test_les_resultats_suivent_l_ordre_de_la_configuration():
    async def gestionnaire(requete: httpx.Request) -> httpx.Response:
        # Le premier site répond le plus tard : l'ordre doit quand même être conservé.
        await asyncio.sleep(0.2 if requete.url.host == "lent.test" else 0)
        return httpx.Response(200)

    resultats = lancer(config_pour("https://lent.test", "https://rapide.test"), gestionnaire)
    assert [resultat.url for resultat in resultats] == ["https://lent.test", "https://rapide.test"]


def test_la_sonde_s_identifie():
    agents = []

    def gestionnaire(requete: httpx.Request) -> httpx.Response:
        agents.append(requete.headers["User-Agent"])
        return httpx.Response(200)

    lancer(config_pour("https://a.test"), gestionnaire)
    assert agents == [AGENT]
    assert AGENT.startswith("vigie/")
    # un moyen de contact est exigé par certains sites (politique robots de Wikipédia)
    assert "https://github.com/LamaJoker/vigie" in AGENT


def test_la_date_contient_le_fuseau_horaire():
    [resultat] = lancer(config_pour("https://a.test"), lambda requete: httpx.Response(200))
    assert datetime.fromisoformat(resultat.date).tzinfo is not None
