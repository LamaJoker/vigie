"""Lot 8.2 : une page qui ne ment pas.

- les heures s'affichent dans le fuseau configuré, et la page le dit ;
- des mesures trop vieilles (la sonde ne tourne plus ?) sont signalées, pas affichées en vert.

Les tests utilisent le fuseau Asia/Tokyo : il diffère de celui de la machine de test
(Paris sur le poste, UTC dans la CI), donc un affichage à l'heure de la machine échoue.
"""

from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

import pytest
from fastapi.testclient import TestClient

from vigie import base
from vigie.api import creer_app
from vigie.config import Configuration, ErreurConfiguration, Site, analyser, charger
from vigie.sonde import Resultat

A = "https://a.test"
B = "https://b.test"
SITES = (Site("Site A", A), Site("Site B", B))


def maintenant() -> datetime:
    return datetime.now(UTC).replace(microsecond=0)


def mesure(url: str, il_y_a: timedelta, etat: str = "UP", code: int | None = 200) -> Resultat:
    date = maintenant() - il_y_a
    return Resultat(date.isoformat(), url, url, etat, code, 100, None)


def enregistrer(url_base: str, *resultats: Resultat) -> None:
    with base.connecter(url_base) as conn:
        base.enregistrer(conn, resultats)


def client(url_base: str, **reglages) -> TestClient:
    return TestClient(creer_app(Configuration(sites=SITES, **reglages), url_base))


# ------------------------------------------------------------- configuration


def un_site(**sections) -> dict:
    return {"sites": [{"url": A}], **sections}


def test_le_fuseau_par_defaut_est_utc():
    assert analyser(un_site()).fuseau == "UTC"


def test_le_fuseau_est_reglable():
    assert analyser(un_site(affichage={"fuseau": "Europe/Paris"})).fuseau == "Europe/Paris"


@pytest.mark.parametrize("fuseau", ["Mars/Olympus", "", "Europe", "../../etc/passwd", 42])
def test_un_fuseau_inconnu_est_refuse(fuseau):
    with pytest.raises(ErreurConfiguration, match="fuseau"):
        analyser(un_site(affichage={"fuseau": fuseau}))


def test_une_section_affichage_mal_formee_est_refusee():
    with pytest.raises(ErreurConfiguration, match=r"\[affichage\]"):
        analyser(un_site(affichage="Europe/Paris"))


@pytest.mark.parametrize(
    ("secondes", "texte"),
    [
        (0, "0 s"),
        (45, "45 s"),
        (60, "1 min"),
        (59 * 60 + 59, "59 min"),
        (7200, "2 h"),
        (7500, "2 h 5 min"),
        (86400, "1 j"),
        (3 * 86400 + 4 * 3600 + 59, "3 j 4 h"),
        (-5, "0 s"),
    ],
)
def test_formater_age(secondes, texte):
    assert base.formater_age(secondes) == texte


def test_l_intervalle_par_defaut_est_de_5_minutes():
    assert analyser(un_site()).intervalle == 300


def test_l_intervalle_est_reglable():
    assert analyser(un_site(sonde={"intervalle": 60})).intervalle == 60


@pytest.mark.parametrize("intervalle", [0, -5, "60", True])
def test_un_intervalle_invalide_est_refuse(intervalle):
    with pytest.raises(ErreurConfiguration, match="intervalle"):
        analyser(un_site(sonde={"intervalle": intervalle}))


@pytest.fixture
def fichier_intervalle_60(tmp_path):
    fichier = tmp_path / "vigie.toml"
    fichier.write_text(f'[sonde]\nintervalle = 60\n\n[[sites]]\nurl = "{A}"\n', encoding="utf-8")
    return fichier


def test_vigie_intervalle_remplace_la_configuration(fichier_intervalle_60, monkeypatch):
    monkeypatch.setenv("VIGIE_INTERVALLE", "5")
    assert charger(fichier_intervalle_60).intervalle == 5


def test_vigie_intervalle_vide_est_ignoree(fichier_intervalle_60, monkeypatch):
    monkeypatch.setenv("VIGIE_INTERVALLE", "")
    assert charger(fichier_intervalle_60).intervalle == 60


@pytest.mark.parametrize("valeur", ["abc", "0", "-3"])
def test_vigie_intervalle_invalide_est_refusee(fichier_intervalle_60, monkeypatch, valeur):
    monkeypatch.setenv("VIGIE_INTERVALLE", valeur)
    with pytest.raises(ErreurConfiguration, match="VIGIE_INTERVALLE"):
        charger(fichier_intervalle_60)


# --------------------------------------------------------------- fuseau horaire


def test_la_page_affiche_l_heure_du_fuseau_configure(base_vide):
    enregistrer(base_vide, mesure(A, timedelta(minutes=1)), mesure(B, timedelta(minutes=1)))
    [site_a, _] = client(base_vide, fuseau="Asia/Tokyo").get("/api/sites").json()
    date = datetime.fromisoformat(site_a["date"])

    page = client(base_vide, fuseau="Asia/Tokyo").get("/").text

    assert date.astimezone(ZoneInfo("Asia/Tokyo")).strftime("%d/%m %H:%M:%S") in page
    assert "Asia/Tokyo" in page  # la page dit dans quel fuseau elle affiche
    # l'heure exacte reste lisible par une machine, en UTC
    assert f'<time datetime="{date.astimezone(UTC).isoformat()}"' in page


def test_les_incidents_s_affichent_aussi_dans_le_fuseau_configure(base_vide):
    from vigie import alertes

    panne = mesure(A, timedelta(minutes=2), "DOWN", 503)
    with base.connecter(base_vide) as conn:
        base.enregistrer(conn, [panne])
        alertes.mettre_a_jour_incidents(conn, [panne], echecs_avant_alerte=1)
    debut = datetime.fromisoformat(panne.date)

    page = client(base_vide, fuseau="Asia/Tokyo").get("/").text

    assert debut.astimezone(ZoneInfo("Asia/Tokyo")).strftime("%d/%m %H:%M") in page


# ------------------------------------------------------------ mesures périmées


def test_des_mesures_recentes_ne_sont_pas_perimees(base_vide):
    enregistrer(base_vide, mesure(A, timedelta(minutes=1)), mesure(B, timedelta(minutes=1)))
    reponse = client(base_vide, intervalle=300)

    sites = reponse.get("/api/sites").json()
    assert [site["perime"] for site in sites] == [False, False]
    assert 50 <= sites[0]["age_secondes"] <= 120
    assert "Tous les sites répondent" in reponse.get("/").text


def test_des_mesures_trop_vieilles_sont_signalees(base_vide):
    deux_heures = timedelta(hours=2)
    enregistrer(base_vide, mesure(A, deux_heures), mesure(B, deux_heures))
    reponse = client(base_vide, intervalle=300)

    sites = reponse.get("/api/sites").json()
    assert [site["perime"] for site in sites] == [True, True]
    assert 7100 <= sites[0]["age_secondes"] <= 7300

    page = reponse.get("/").text
    assert "Mesures périmées" in page
    assert "il y a 2 h" in page
    assert "Tous les sites répondent" not in page  # avant le lot 8.2 : bandeau vert


def test_le_seuil_est_de_trois_intervalles(base_vide):
    enregistrer(base_vide, mesure(A, timedelta(seconds=170)), mesure(B, timedelta(seconds=190)))
    sites = client(base_vide, intervalle=60).get("/api/sites").json()
    assert [site["perime"] for site in sites] == [False, True]


def test_un_site_jamais_mesure_n_est_pas_dit_perime(base_vide):
    enregistrer(base_vide, mesure(A, timedelta(minutes=1)))
    [_, site_b] = client(base_vide).get("/api/sites").json()
    assert site_b["perime"] is False
    assert site_b["age_secondes"] is None


def test_une_vieille_panne_n_est_pas_affichee_comme_panne_actuelle(base_vide):
    deux_heures = timedelta(hours=2)
    enregistrer(base_vide, mesure(A, deux_heures, "DOWN", 503), mesure(B, deux_heures))
    page = client(base_vide, intervalle=300).get("/").text
    assert "en panne" not in page
    assert "Mesures périmées" in page


def test_une_panne_recente_reste_affichee_en_premier(base_vide):
    enregistrer(
        base_vide,
        mesure(A, timedelta(minutes=1), "DOWN", 503),
        mesure(B, timedelta(hours=2)),
    )
    page = client(base_vide, intervalle=300).get("/").text
    assert "1 site en panne : Site A" in page
