"""Tests de la rétention des mesures (lot 8.3) : réglage, purge, commande, purge quotidienne."""

from datetime import timedelta
from pathlib import Path

import pytest
from outils import resultat

from vigie import alertes, base, cli
from vigie.cli import main
from vigie.config import ErreurConfiguration, analyser, charger

A = "https://a.test"
SITES = {"sites": [{"url": A}]}
BASE_INJOIGNABLE = "postgresql://vigie@/aucune?host=/dossier/inexistant&port=1"
CONFIG_FOURNIE = Path(__file__).parents[2] / "config" / "vigie.toml"


@pytest.fixture
def conn(base_vide):
    with base.connecter(base_vide) as connexion:
        yield connexion


def compter(conn, table: str) -> int:
    return conn.execute(f"SELECT count(*) AS n FROM {table}").fetchone()["n"]


# --- Le réglage ---------------------------------------------------------------------


def test_retention_de_90_jours_par_defaut():
    assert analyser(SITES).retention_jours == 90


def test_retention_reglable():
    assert analyser({**SITES, "retention": {"jours": 7}}).retention_jours == 7


def test_la_configuration_fournie_garde_90_jours():
    assert charger(CONFIG_FOURNIE).retention_jours == 90


@pytest.mark.parametrize("jours", [0, -1, 1.5, "90", True])
def test_retention_invalide(jours):
    with pytest.raises(ErreurConfiguration, match="retention.jours"):
        analyser({**SITES, "retention": {"jours": jours}})


def test_section_retention_mal_formee():
    with pytest.raises(ErreurConfiguration, match=r"\[retention\]"):
        analyser({**SITES, "retention": 90})


# --- La purge -----------------------------------------------------------------------


def test_purger_supprime_seulement_les_mesures_trop_vieilles(conn):
    base.enregistrer(
        conn,
        [
            resultat(A, il_y_a=timedelta(days=100)),
            resultat(A, il_y_a=timedelta(days=89)),
            resultat(A, il_y_a=timedelta(minutes=1)),
        ],
    )
    assert base.purger(conn, 90) == 1
    assert compter(conn, "sondes") == 2


def test_purger_garde_les_incidents(conn):
    vieille_panne = resultat(A, "DOWN", 503, il_y_a=timedelta(days=200))
    base.enregistrer(conn, [vieille_panne])
    alertes.mettre_a_jour_incidents(conn, [vieille_panne], echecs_avant_alerte=1)
    assert compter(conn, "incidents") == 1

    assert base.purger(conn, 90) == 1

    assert compter(conn, "sondes") == 0
    assert compter(conn, "incidents") == 1


def test_purger_par_petits_lots(conn):
    base.enregistrer(conn, [resultat(A, il_y_a=timedelta(days=100 + n)) for n in range(5)])
    assert base.purger(conn, 90, lot=2) == 5
    assert compter(conn, "sondes") == 0


def test_purger_sans_vieilles_mesures(conn):
    base.enregistrer(conn, [resultat(A)])
    assert base.purger(conn, 90) == 0
    assert compter(conn, "sondes") == 1


# --- La commande « vigie purger » -----------------------------------------------------


def test_vigie_purger(base_vide, ecrire_config, capsys):
    with base.connecter(base_vide) as connexion:
        base.enregistrer(
            connexion, [resultat(A, il_y_a=timedelta(days=10)), resultat(A, il_y_a=timedelta(1))]
        )
    config = ecrire_config([A], retention=7)

    assert main(["purger", "--config", str(config), "--base", base_vide]) == 0

    sortie = capsys.readouterr().out
    assert "plus de 7 jours" in sortie
    assert "1 supprimée" in sortie
    with base.connecter(base_vide) as connexion:
        assert compter(connexion, "sondes") == 1


def test_vigie_purger_sans_adresse(ecrire_config, capsys):
    assert main(["purger", "--config", str(ecrire_config([A]))]) == 2
    assert "VIGIE_DATABASE_URL" in capsys.readouterr().err


def test_vigie_purger_base_injoignable(ecrire_config, capsys):
    config = ecrire_config([A])
    assert main(["purger", "--config", str(config), "--base", BASE_INJOIGNABLE]) == 2
    assert "purge des anciennes mesures impossible" in capsys.readouterr().err


def test_vigie_purger_configuration_absente(tmp_path, capsys):
    absente = str(tmp_path / "absente.toml")
    assert main(["purger", "--config", absente, "--base", BASE_INJOIGNABLE]) == 2
    assert "introuvable" in capsys.readouterr().err


# --- La purge quotidienne de « vigie surveiller » --------------------------------------


def surveiller(config, tmp_path, url_base, passages):
    log = tmp_path / "sondes.jsonl"
    options = ["--config", str(config), "--log", str(log), "--intervalle", "0"]
    if url_base:
        options += ["--base", url_base]
    return main(["surveiller", *options, "--passages", str(passages)])


def test_surveiller_purge_des_le_premier_passage(serveur, base_vide, ecrire_config, tmp_path):
    with base.connecter(base_vide) as connexion:
        base.enregistrer(connexion, [resultat(A, il_y_a=timedelta(days=100))])
    config = ecrire_config([f"{serveur}/200"])

    assert surveiller(config, tmp_path, base_vide, passages=1) == 0

    with base.connecter(base_vide) as connexion:
        urls = [ligne["url"] for ligne in connexion.execute("SELECT url FROM sondes")]
    assert urls == [f"{serveur}/200"]  # la vieille mesure est partie, la nouvelle est là


def test_surveiller_purge_une_fois_par_jour(
    serveur, base_vide, ecrire_config, tmp_path, monkeypatch
):
    # Horloge simulée : passages à 0 s, 1 h, puis 25 h.
    horloge = iter([0.0, 3600.0, 90000.0])
    monkeypatch.setattr(cli, "monotonic", lambda: next(horloge))
    purges = []
    monkeypatch.setattr(cli, "purger_en_base", lambda url, jours: purges.append(jours) or 0)
    config = ecrire_config([f"{serveur}/200"], retention=30)

    assert surveiller(config, tmp_path, base_vide, passages=3) == 0

    assert purges == [30, 30]  # au premier passage, puis 24 h plus tard


def test_surveiller_reessaie_une_purge_qui_a_echoue(
    serveur, base_vide, ecrire_config, tmp_path, monkeypatch
):
    horloge = iter([0.0, 1.0, 2.0])
    monkeypatch.setattr(cli, "monotonic", lambda: next(horloge))
    reponses = iter([None, 0])  # None : la purge a échoué
    purges = []
    monkeypatch.setattr(
        cli, "purger_en_base", lambda url, jours: purges.append(jours) or next(reponses)
    )
    config = ecrire_config([f"{serveur}/200"])

    assert surveiller(config, tmp_path, base_vide, passages=3) == 0

    assert len(purges) == 2  # échec au passage 1, réussite au passage 2, rien au passage 3


def test_surveiller_ne_purge_pas_sans_base(serveur, ecrire_config, tmp_path, monkeypatch):
    def interdite(url, jours):
        raise AssertionError("purge sans base")

    monkeypatch.setattr(cli, "purger_en_base", interdite)
    config = ecrire_config([f"{serveur}/200"])
    assert surveiller(config, tmp_path, None, passages=2) == 0


def test_surveiller_ne_purge_pas_quand_la_base_est_injoignable(
    serveur, ecrire_config, tmp_path, monkeypatch, capsys
):
    # Le passage a déjà signalé la base injoignable : inutile d'ajouter une deuxième erreur.
    def interdite(url, jours):
        raise AssertionError("purge alors que la base est injoignable")

    monkeypatch.setattr(cli, "purger_en_base", interdite)
    config = ecrire_config([f"{serveur}/200"])
    assert surveiller(config, tmp_path, BASE_INJOIGNABLE, passages=2) == 0
    assert capsys.readouterr().err.count("enregistrement en base impossible") == 2
