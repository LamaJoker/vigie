"""Lot 8.2 : « vigie sante-sonde » et l'intervalle de « vigie surveiller ».

sante-sonde sert de contrôle de santé au conteneur de la sonde : il répond 0 si une
mesure récente existe en base, 1 sinon. Une sonde qui tourne mais n'enregistre plus
rien (base injoignable...) est ainsi vue comme malade.
"""

from datetime import UTC, datetime, timedelta

from vigie import base, cli
from vigie.cli import main
from vigie.sonde import Resultat

A = "https://a.test"
BASE_INJOIGNABLE = "postgresql://vigie@/aucune?host=/dossier/inexistant&port=1"


def enregistrer(url_base: str, url: str, il_y_a: timedelta) -> None:
    date = (datetime.now(UTC) - il_y_a).isoformat(timespec="seconds")
    with base.connecter(url_base) as conn:
        base.enregistrer(conn, [Resultat(date, url, url, "UP", 200, 80, None)])


def sante(config, url_base):
    return main(["sante-sonde", "--config", str(config), "--base", url_base])


def test_sante_sonde_avec_une_mesure_recente(base_vide, ecrire_config, capsys):
    config = ecrire_config([A], intervalle=60)
    enregistrer(base_vide, A, timedelta(seconds=30))
    assert sante(config, base_vide) == 0
    assert "dernière mesure il y a" in capsys.readouterr().out


def test_sante_sonde_avec_une_mesure_trop_vieille(base_vide, ecrire_config, capsys):
    config = ecrire_config([A], intervalle=60)
    enregistrer(base_vide, A, timedelta(minutes=10))  # seuil : 3 x 60 s
    assert sante(config, base_vide) == 1
    assert "trop vieille" in capsys.readouterr().err


def test_sante_sonde_sans_aucune_mesure(base_vide, ecrire_config, capsys):
    assert sante(ecrire_config([A]), base_vide) == 1
    assert "aucune mesure" in capsys.readouterr().err


def test_sante_sonde_ignore_les_sites_qui_ne_sont_plus_surveilles(base_vide, ecrire_config, capsys):
    enregistrer(base_vide, "https://ancien.test", timedelta(seconds=5))
    assert sante(ecrire_config([A]), base_vide) == 1


def test_sante_sonde_base_injoignable(ecrire_config, capsys):
    assert sante(ecrire_config([A]), BASE_INJOIGNABLE) == 1
    assert "injoignable" in capsys.readouterr().err


def test_sante_sonde_sans_adresse_de_base(ecrire_config):
    assert main(["sante-sonde", "--config", str(ecrire_config([A]))]) == 2


def test_sante_sonde_configuration_absente(tmp_path):
    absente = str(tmp_path / "absente.toml")
    assert main(["sante-sonde", "--config", absente, "--base", BASE_INJOIGNABLE]) == 2


# ------------------------------------------------- intervalle de « surveiller »


class EvenementInstantane:
    """Remplace l'Event de vigie.cli (et lui seul) : note les attentes sans attendre."""

    attentes: list[float] = []

    def __init__(self) -> None:
        self.leve = False

    def is_set(self) -> bool:
        return self.leve

    def set(self) -> None:
        self.leve = True

    def wait(self, delai: float | None = None) -> bool:
        EvenementInstantane.attentes.append(delai)
        return self.leve


def attentes_de_surveiller(monkeypatch, config, tmp_path, *options) -> list[float]:
    EvenementInstantane.attentes = []
    monkeypatch.setattr(cli, "Event", EvenementInstantane)
    log = tmp_path / "sondes.jsonl"
    code = main(
        ["surveiller", "--config", str(config), "--log", str(log), "--passages", "3", *options]
    )
    assert code == 0
    return EvenementInstantane.attentes


def test_surveiller_prend_l_intervalle_de_la_configuration(
    serveur, ecrire_config, tmp_path, monkeypatch
):
    config = ecrire_config([f"{serveur}/200"], intervalle=42)
    assert attentes_de_surveiller(monkeypatch, config, tmp_path) == [42, 42]


def test_vigie_intervalle_prime_sur_la_configuration(serveur, ecrire_config, tmp_path, monkeypatch):
    monkeypatch.setenv("VIGIE_INTERVALLE", "7")
    config = ecrire_config([f"{serveur}/200"], intervalle=42)
    assert attentes_de_surveiller(monkeypatch, config, tmp_path) == [7, 7]


def test_l_option_intervalle_prime_sur_tout(serveur, ecrire_config, tmp_path, monkeypatch):
    monkeypatch.setenv("VIGIE_INTERVALLE", "7")
    config = ecrire_config([f"{serveur}/200"], intervalle=42)
    assert attentes_de_surveiller(monkeypatch, config, tmp_path, "--intervalle", "2") == [2, 2]
