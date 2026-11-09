"""Tests de l'API et de la page de statut, avec une vraie base jetable."""

from datetime import timedelta

import pytest
from fastapi.testclient import TestClient
from outils import resultat

from vigie import base
from vigie.api import creer_app
from vigie.config import Configuration, Site

A = "https://a.test"
B = "https://b.test"
CONFIG = Configuration(sites=(Site("Site A", A), Site("Site B", B)))
BASE_INJOIGNABLE = "postgresql://vigie@/aucune?host=/dossier/inexistant&port=1"


@pytest.fixture
def client(base_vide):
    return TestClient(creer_app(CONFIG, base_vide))


@pytest.fixture
def remplir(base_vide):
    def _remplir(*resultats):
        with base.connecter(base_vide) as conn:
            base.enregistrer(conn, resultats)

    return _remplir


def test_sante(client):
    reponse = client.get("/sante")
    assert reponse.status_code == 200
    assert reponse.json() == {"statut": "ok", "base": "ok"}


def test_sante_quand_la_base_est_injoignable():
    client = TestClient(creer_app(CONFIG, BASE_INJOIGNABLE))
    reponse = client.get("/sante")
    assert reponse.status_code == 503
    assert reponse.json()["base"] == "injoignable"


def test_api_sites(client, remplir):
    remplir(resultat(A, "DOWN", 503, nom="Site A"))
    reponse = client.get("/api/sites")
    assert reponse.status_code == 200
    [site_a, site_b] = reponse.json()
    assert site_a["nom"] == "Site A"
    assert site_a["etat"] == "DOWN"
    assert site_a["code"] == 503
    assert site_a["disponibilite"] == 0
    assert site_b["etat"] is None


def test_api_quand_la_base_est_injoignable():
    client = TestClient(creer_app(CONFIG, BASE_INJOIGNABLE))
    reponse = client.get("/api/sites")
    assert reponse.status_code == 503
    assert "injoignable" in reponse.json()["detail"]


def test_historique(client, remplir):
    remplir(*(resultat(A, il_y_a=timedelta(minutes=minutes)) for minutes in range(3)))
    reponse = client.get("/api/sites/historique", params={"url": A, "limite": 2})
    assert reponse.status_code == 200
    assert len(reponse.json()) == 2


def test_historique_d_un_site_inconnu(client):
    reponse = client.get("/api/sites/historique", params={"url": "https://inconnu.test"})
    assert reponse.status_code == 404


@pytest.mark.parametrize("limite", [0, 1001, "beaucoup"])
def test_historique_limite_invalide(client, limite):
    reponse = client.get("/api/sites/historique", params={"url": A, "limite": limite})
    assert reponse.status_code == 422


def test_page_sans_mesure(client):
    reponse = client.get("/")
    assert reponse.status_code == 200
    assert "text/html" in reponse.headers["content-type"]
    assert "Aucune mesure" in reponse.text


def test_page_quand_tout_va_bien(client, remplir):
    remplir(resultat(A), resultat(B))
    page = client.get("/").text
    assert "Tous les sites répondent" in page
    assert "Site A" in page and "Site B" in page
    assert "100,0 %" in page


def test_page_avec_une_panne(client, remplir):
    remplir(resultat(A), resultat(B, "DOWN", None, erreur="pas de réponse en 10 s"))
    page = client.get("/").text
    assert "1 site en panne : Site B" in page
    assert "pas de réponse en 10 s" in page


def test_la_page_protege_contre_l_injection_html(remplir, base_vide):
    # Un nom piégé dans la configuration ne doit jamais devenir du code dans la page.
    config = Configuration(sites=(Site("<script>alert(1)</script>", A),))
    remplir(resultat(A))
    page = TestClient(creer_app(config, base_vide)).get("/").text
    assert "<script>alert(1)</script>" not in page
    assert "&lt;script&gt;" in page


def test_la_documentation_de_l_api_est_publiee(client):
    assert client.get("/docs").status_code == 200
    assert client.get("/openapi.json").json()["info"]["title"] == "Vigie"
