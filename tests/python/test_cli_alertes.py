"""Scénarios complets d'alerte : un vrai site local qu'on fait tomber, un faux Discord."""

from conftest import Gestionnaire

from vigie.cli import main


def sonder(config, base, tmp_path):
    log = tmp_path / "sondes.jsonl"
    return main(["sonder", "--config", str(config), "--log", str(log), "--base", base])


def titres_recus():
    return [message["embeds"][0]["title"] for message in Gestionnaire.recus]


def test_une_alerte_a_la_panne_une_au_retour_et_rien_d_autre(
    serveur, webhook, ecrire_config, tmp_path, base_vide, monkeypatch, capsys
):
    monkeypatch.setenv("VIGIE_DISCORD_WEBHOOK", webhook)
    config = ecrire_config([f"{serveur}/bascule"], echecs_avant_alerte=2)

    assert sonder(config, base_vide, tmp_path) == 0  # en ligne
    Gestionnaire.code_bascule = 503
    assert sonder(config, base_vide, tmp_path) == 1  # 1er échec : pas encore d'alerte
    assert titres_recus() == []
    assert sonder(config, base_vide, tmp_path) == 1  # 2e échec : alerte de panne
    assert titres_recus() == ["🔴 Panne : site 1"]
    assert sonder(config, base_vide, tmp_path) == 1  # la panne continue : rien de plus
    assert titres_recus() == ["🔴 Panne : site 1"]

    Gestionnaire.code_bascule = 200
    assert sonder(config, base_vide, tmp_path) == 0  # retour : alerte de rétablissement
    assert sonder(config, base_vide, tmp_path) == 0  # tout va bien : rien de plus
    assert titres_recus() == ["🔴 Panne : site 1", "🟢 Rétabli : site 1"]

    sortie = capsys.readouterr().out
    assert "site 1 est en panne (code HTTP 503)" in sortie
    assert "site 1 est rétabli après" in sortie


def test_sans_webhook_les_alertes_sont_affichees_une_seule_fois(
    serveur, webhook, ecrire_config, tmp_path, base_vide, capsys
):
    config = ecrire_config([f"{serveur}/503"], echecs_avant_alerte=1)

    assert sonder(config, base_vide, tmp_path) == 1
    capture = capsys.readouterr()
    assert "est en panne" in capture.out
    assert "VIGIE_DISCORD_WEBHOOK n'est pas définie" in capture.err

    assert sonder(config, base_vide, tmp_path) == 1
    assert "est en panne" not in capsys.readouterr().out


def test_une_alerte_bloquee_par_discord_repart_au_passage_suivant(
    serveur, webhook, ecrire_config, tmp_path, base_vide, monkeypatch, capsys
):
    config = ecrire_config([f"{serveur}/503"], echecs_avant_alerte=1)

    monkeypatch.setenv("VIGIE_DISCORD_WEBHOOK", f"{serveur}/webhook-500")
    assert sonder(config, base_vide, tmp_path) == 1
    erreurs = capsys.readouterr().err
    assert "nouvel essai au prochain passage" in erreurs
    assert "code 500" in erreurs
    assert "webhook-500" not in erreurs  # l'adresse du webhook n'est jamais affichée
    assert titres_recus() == []

    monkeypatch.setenv("VIGIE_DISCORD_WEBHOOK", webhook)
    assert sonder(config, base_vide, tmp_path) == 1
    assert titres_recus() == ["🔴 Panne : site 1"]


def test_tester_alerte_sans_webhook(capsys):
    assert main(["tester-alerte"]) == 2
    assert ".env.exemple" in capsys.readouterr().err


def test_tester_alerte(webhook, monkeypatch, capsys):
    monkeypatch.setenv("VIGIE_DISCORD_WEBHOOK", webhook)
    assert main(["tester-alerte"]) == 0
    assert titres_recus() == ["🔴 Panne : Essai de Vigie"]
    assert "envoyée" in capsys.readouterr().out


def test_tester_alerte_quand_discord_refuse(serveur, webhook, monkeypatch, capsys):
    monkeypatch.setenv("VIGIE_DISCORD_WEBHOOK", f"{serveur}/webhook-404")
    assert main(["tester-alerte"]) == 2
    assert "code 404" in capsys.readouterr().err
