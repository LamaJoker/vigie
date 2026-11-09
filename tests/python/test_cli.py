"""Tests de bout en bout de la commande « vigie sonder », contre un vrai serveur local."""

import fcntl
import json
import subprocess
import sys

import pytest

from vigie import __version__
from vigie.cli import main


def lire_journal(chemin) -> list[dict]:
    return [json.loads(ligne) for ligne in chemin.read_text(encoding="utf-8").splitlines()]


def test_tous_les_sites_repondent(serveur, ecrire_config, tmp_path, capsys):
    config = ecrire_config([f"{serveur}/200", f"{serveur}/redirection"])
    log = tmp_path / "sondes.jsonl"

    assert main(["sonder", "--config", str(config), "--log", str(log)]) == 0

    lignes = lire_journal(log)
    assert [ligne["etat"] for ligne in lignes] == ["UP", "UP"]
    assert set(lignes[0]) == {"date", "nom", "url", "etat", "code", "duree_ms", "erreur"}
    assert "UP" in capsys.readouterr().out


def test_une_panne_donne_le_code_de_sortie_1(serveur, ecrire_config, tmp_path):
    config = ecrire_config([f"{serveur}/200", f"{serveur}/503"])
    log = tmp_path / "sondes.jsonl"

    assert main(["sonder", "--config", str(config), "--log", str(log)]) == 1
    assert [ligne["code"] for ligne in lire_journal(log)] == [200, 503]


def test_un_site_injoignable_est_note_sans_code(ecrire_config, tmp_path, capsys):
    config = ecrire_config(["http://127.0.0.1:1/"])
    log = tmp_path / "sondes.jsonl"

    assert main(["sonder", "--config", str(config), "--log", str(log)]) == 1
    [ligne] = lire_journal(log)
    assert ligne["code"] is None
    assert ligne["erreur"]
    assert "---" in capsys.readouterr().out


def test_un_site_lent_est_abandonne(serveur, ecrire_config, tmp_path):
    config = ecrire_config([f"{serveur}/lent"], delai=0.5)
    log = tmp_path / "sondes.jsonl"

    assert main(["sonder", "--config", str(config), "--log", str(log)]) == 1
    [ligne] = lire_journal(log)
    assert ligne["etat"] == "DOWN"
    assert 400 <= ligne["duree_ms"] < 2000


def test_les_resultats_s_ajoutent_sans_ecraser(serveur, ecrire_config, tmp_path):
    config = ecrire_config([f"{serveur}/200"])
    log = tmp_path / "sondes.jsonl"

    main(["sonder", "--config", str(config), "--log", str(log)])
    main(["sonder", "--config", str(config), "--log", str(log)])
    assert len(lire_journal(log)) == 2


def test_configuration_absente(tmp_path, capsys):
    code = main(["sonder", "--config", str(tmp_path / "absent.toml")])
    assert code == 2
    assert "introuvable" in capsys.readouterr().err


def test_variables_d_environnement(serveur, ecrire_config, tmp_path, monkeypatch):
    config = ecrire_config([f"{serveur}/200"])
    log = tmp_path / "depuis-env.jsonl"
    monkeypatch.setenv("VIGIE_CONFIG", str(config))
    monkeypatch.setenv("VIGIE_LOG", str(log))

    assert main(["sonder"]) == 0
    assert len(lire_journal(log)) == 1


def test_log_par_defaut_dans_le_dossier_xdg(serveur, ecrire_config, tmp_path, monkeypatch):
    config = ecrire_config([f"{serveur}/200"])
    monkeypatch.delenv("VIGIE_LOG", raising=False)
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path / "state"))

    assert main(["sonder", "--config", str(config)]) == 0
    assert (tmp_path / "state" / "vigie" / "sondes.jsonl").exists()


def test_deux_sondes_ne_tournent_jamais_en_meme_temps(serveur, ecrire_config, tmp_path, capsys):
    config = ecrire_config([f"{serveur}/200"])
    log = tmp_path / "sondes.jsonl"

    with open(tmp_path / "sondes.jsonl.verrou", "w") as verrou:
        fcntl.flock(verrou, fcntl.LOCK_EX)  # une autre sonde « tourne déjà »
        assert main(["sonder", "--config", str(config), "--log", str(log)]) == 0

    assert "déjà en cours" in capsys.readouterr().err
    assert not log.exists()


def test_une_commande_est_obligatoire():
    with pytest.raises(SystemExit) as sortie:
        main([])
    assert sortie.value.code == 2


def test_python_m_vigie_affiche_la_version():
    sortie = subprocess.run(
        [sys.executable, "-m", "vigie", "--version"], capture_output=True, text=True, check=True
    )
    assert __version__ in sortie.stdout
