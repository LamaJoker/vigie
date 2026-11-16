"""Tests de « vigie surveiller » : la boucle qui tourne dans le conteneur de la sonde."""

import os
import signal
import threading
import time

from vigie import cli
from vigie.cli import main


def surveiller(config, tmp_path, *options):
    log = tmp_path / "sondes.jsonl"
    return main(["surveiller", "--config", str(config), "--log", str(log), *options]), log


def test_une_erreur_imprevue_n_arrete_pas_la_surveillance(
    serveur, ecrire_config, tmp_path, monkeypatch, capsys
):
    vraie_commande = cli.commande_sonder
    appels = []

    def un_passage_sur_deux_casse(*arguments):
        appels.append(1)
        if len(appels) % 2 == 1:
            raise RuntimeError("bug imprévu")
        return vraie_commande(*arguments)

    monkeypatch.setattr(cli, "commande_sonder", un_passage_sur_deux_casse)
    config = ecrire_config([f"{serveur}/200"])

    code, log = surveiller(config, tmp_path, "--intervalle", "0", "--passages", "4")

    assert code == 0
    assert len(appels) == 4
    assert len(log.read_text(encoding="utf-8").splitlines()) == 2  # les passages réussis
    erreurs = capsys.readouterr().err
    assert erreurs.count("erreur imprévue") == 2
    assert "RuntimeError: bug imprévu" in erreurs  # la trace complète est gardée


def test_cinq_erreurs_imprevues_de_suite_arretent_la_surveillance(
    serveur, ecrire_config, tmp_path, monkeypatch, capsys
):
    def toujours_casse(*arguments):
        raise RuntimeError("bug permanent")

    monkeypatch.setattr(cli, "commande_sonder", toujours_casse)
    config = ecrire_config([f"{serveur}/200"])

    # Sans --passages, la boucle est infinie : seul le garde-fou peut l'arrêter.
    code, _ = surveiller(config, tmp_path, "--intervalle", "0")

    assert code == 1
    erreurs = capsys.readouterr().err
    assert "(5/5 de suite)" in erreurs
    assert "arrêt pour être relancé" in erreurs


def test_un_nombre_de_passages_donne(serveur, ecrire_config, tmp_path, capsys):
    config = ecrire_config([f"{serveur}/200"])
    code, log = surveiller(config, tmp_path, "--intervalle", "0", "--passages", "3")
    assert code == 0
    assert len(log.read_text(encoding="utf-8").splitlines()) == 3
    assert "--- passage 3" in capsys.readouterr().out


def test_une_panne_n_arrete_pas_la_surveillance(serveur, ecrire_config, tmp_path):
    config = ecrire_config([f"{serveur}/503"])
    code, log = surveiller(config, tmp_path, "--intervalle", "0", "--passages", "2")
    assert code == 0
    assert len(log.read_text(encoding="utf-8").splitlines()) == 2


def test_sigterm_arrete_proprement(serveur, ecrire_config, tmp_path, capsys):
    config = ecrire_config([f"{serveur}/200"])
    # Comme « docker stop » : SIGTERM envoyé pendant l'attente entre deux passages.
    threading.Timer(0.5, os.kill, (os.getpid(), signal.SIGTERM)).start()
    debut = time.perf_counter()

    code, log = surveiller(config, tmp_path, "--intervalle", "60")

    assert code == 0
    assert time.perf_counter() - debut < 5  # n'a pas attendu les 60 secondes
    assert "SIGTERM reçu" in capsys.readouterr().err
    assert len(log.read_text(encoding="utf-8").splitlines()) == 1


def test_les_gestionnaires_de_signaux_sont_remis_en_place(serveur, ecrire_config, tmp_path):
    avant = signal.getsignal(signal.SIGTERM)
    config = ecrire_config([f"{serveur}/200"])
    surveiller(config, tmp_path, "--intervalle", "0", "--passages", "1")
    assert signal.getsignal(signal.SIGTERM) is avant


def test_une_configuration_invalide_arrete_tout_de_suite(tmp_path, capsys):
    code, _ = surveiller(tmp_path / "absente.toml", tmp_path, "--intervalle", "0")
    assert code == 2
    assert "introuvable" in capsys.readouterr().err


def test_options_negatives_refusees(serveur, ecrire_config, tmp_path):
    config = ecrire_config([f"{serveur}/200"])
    assert surveiller(config, tmp_path, "--intervalle", "-1")[0] == 2
    assert surveiller(config, tmp_path, "--passages", "-1")[0] == 2


def test_un_journal_inaccessible_n_arrete_pas_la_surveillance(
    serveur, ecrire_config, tmp_path, capsys
):
    # Cas trouvé par l'essai Docker : dossier de travail interdit en écriture.
    interdit = tmp_path / "interdit"
    interdit.mkdir(mode=0o500)
    config = ecrire_config([f"{serveur}/200"])
    log = interdit / "sondes.jsonl"
    try:
        code = main(
            [
                "surveiller",
                "--config",
                str(config),
                "--log",
                str(log),
                "--intervalle",
                "0",
                "--passages",
                "2",
            ]
        )
    finally:
        interdit.chmod(0o700)
    assert code == 0
    erreurs = capsys.readouterr().err
    assert erreurs.count("journal inaccessible") == 2  # deux passages, aucun plantage


def test_sonder_avec_un_journal_inaccessible(serveur, ecrire_config, tmp_path, capsys):
    interdit = tmp_path / "interdit"
    interdit.mkdir(mode=0o500)
    config = ecrire_config([f"{serveur}/200"])
    try:
        code = main(["sonder", "--config", str(config), "--log", str(interdit / "s.jsonl")])
    finally:
        interdit.chmod(0o700)
    assert code == 2
    assert "journal inaccessible" in capsys.readouterr().err


def test_une_ecriture_impossible_du_journal_est_signalee(serveur, ecrire_config, tmp_path, capsys):
    log = tmp_path / "sondes.jsonl"
    log.mkdir()  # un dossier à la place du fichier : l'écriture échoue
    config = ecrire_config([f"{serveur}/200"])
    code = main(["sonder", "--config", str(config), "--log", str(log)])
    assert code == 0  # la mesure a eu lieu, seul le journal manque
    assert "écriture du journal impossible" in capsys.readouterr().err


def test_intervalle_par_variable_d_environnement(serveur, ecrire_config, tmp_path, monkeypatch):
    monkeypatch.setenv("VIGIE_INTERVALLE", "0")
    config = ecrire_config([f"{serveur}/200"])
    code, log = surveiller(config, tmp_path, "--passages", "2")
    assert code == 0
    assert len(log.read_text(encoding="utf-8").splitlines()) == 2
