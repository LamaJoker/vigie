from pathlib import Path

import pytest

from vigie.config import (
    DELAI_PAR_DEFAUT,
    ECHECS_AVANT_ALERTE_PAR_DEFAUT,
    PARALLELES_PAR_DEFAUT,
    ErreurConfiguration,
    Site,
    analyser,
    charger,
)

RACINE = Path(__file__).resolve().parents[2]


def un_site(**champs):
    return {"sites": [{"url": "https://example.com", **champs}]}


def test_configuration_minimale_avec_valeurs_par_defaut():
    config = analyser(un_site(nom="Exemple"))
    assert config.sites == (Site(nom="Exemple", url="https://example.com"),)
    assert config.delai == DELAI_PAR_DEFAUT
    assert config.paralleles == PARALLELES_PAR_DEFAUT


def test_le_nom_par_defaut_est_l_adresse():
    assert analyser(un_site()).sites[0].nom == "https://example.com"


def test_lecture_d_un_fichier(tmp_path):
    fichier = tmp_path / "vigie.toml"
    fichier.write_text(
        '[sonde]\ndelai = 2.5\nparalleles = 3\n\n[[sites]]\nnom = "A"\nurl = "http://a.test"\n',
        encoding="utf-8",
    )
    config = charger(fichier)
    assert config.delai == 2.5
    assert config.paralleles == 3
    assert config.sites[0].url == "http://a.test"


def test_la_configuration_du_depot_est_valide():
    config = charger(RACINE / "config" / "vigie.toml")
    assert len(config.sites) >= 1


def test_fichier_absent(tmp_path):
    with pytest.raises(ErreurConfiguration, match="introuvable"):
        charger(tmp_path / "absent.toml")


def test_fichier_toml_invalide(tmp_path):
    fichier = tmp_path / "vigie.toml"
    fichier.write_text("[[sites]\nurl = ", encoding="utf-8")
    with pytest.raises(ErreurConfiguration, match="TOML"):
        charger(fichier)


@pytest.mark.parametrize("donnees", [{}, {"sites": []}, {"sites": "https://example.com"}])
def test_au_moins_un_site_est_obligatoire(donnees):
    with pytest.raises(ErreurConfiguration, match="au moins un site"):
        analyser(donnees)


@pytest.mark.parametrize(
    "url", [None, "", "example.com", "ftp://example.com", "https://", "pas une adresse", 42]
)
def test_adresse_invalide(url):
    with pytest.raises(ErreurConfiguration, match="adresse http ou https"):
        analyser({"sites": [{"url": url}]})


def test_adresse_en_double():
    donnees = {"sites": [{"url": "https://example.com"}, {"url": "https://example.com"}]}
    with pytest.raises(ErreurConfiguration, match="en double"):
        analyser(donnees)


@pytest.mark.parametrize("nom", ["", "   ", 12])
def test_nom_invalide(nom):
    with pytest.raises(ErreurConfiguration, match="nom"):
        analyser(un_site(nom=nom))


@pytest.mark.parametrize("delai", [0, -1, "10", True])
def test_delai_invalide(delai):
    with pytest.raises(ErreurConfiguration, match="delai"):
        analyser({"sonde": {"delai": delai}, **un_site()})


@pytest.mark.parametrize("paralleles", [0, 1.5, "4", False])
def test_paralleles_invalide(paralleles):
    with pytest.raises(ErreurConfiguration, match="paralleles"):
        analyser({"sonde": {"paralleles": paralleles}, **un_site()})


def test_section_sonde_mal_formee():
    with pytest.raises(ErreurConfiguration, match=r"\[sonde\]"):
        analyser({"sonde": "rapide", **un_site()})


def test_bloc_de_site_mal_forme():
    with pytest.raises(ErreurConfiguration, match="bloc"):
        analyser({"sites": ["https://example.com"]})


def test_seuil_d_alerte_par_defaut_et_reglable():
    assert analyser(un_site()).echecs_avant_alerte == ECHECS_AVANT_ALERTE_PAR_DEFAUT
    assert analyser({"alertes": {"echecs_avant_alerte": 3}, **un_site()}).echecs_avant_alerte == 3


@pytest.mark.parametrize("echecs", [0, -2, 1.5, "2", True])
def test_seuil_d_alerte_invalide(echecs):
    with pytest.raises(ErreurConfiguration, match="echecs_avant_alerte"):
        analyser({"alertes": {"echecs_avant_alerte": echecs}, **un_site()})


def test_section_alertes_mal_formee():
    with pytest.raises(ErreurConfiguration, match=r"\[alertes\]"):
        analyser({"alertes": ["discord"], **un_site()})
