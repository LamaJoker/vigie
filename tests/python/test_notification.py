"""Tests de l'envoi sur Discord, avec un faux Discord (httpx.MockTransport)."""

import json
from datetime import datetime, timedelta

import httpx
import pytest

from vigie import notification
from vigie.alertes import PANNE, RETABLISSEMENT, Alerte

WEBHOOK = "https://discord.test/api/webhooks/123/jeton-secret"
DEBUT = datetime(2026, 11, 9, 14, 0).astimezone()


def alerte(type_=PANNE, cause="code HTTP 503", numero=1):
    fin = DEBUT + timedelta(minutes=12) if type_ == RETABLISSEMENT else None
    return Alerte(numero, type_, f"Site {numero}", "https://a.test", DEBUT, fin, cause)


class FauxDiscord:
    """Répond les codes demandés, dans l'ordre, et garde les messages reçus."""

    def __init__(self, *codes, retry_after=0.01):
        self.codes = list(codes) or [204]
        self.retry_after = retry_after
        self.recus = []

    def __call__(self, requete: httpx.Request) -> httpx.Response:
        self.recus.append(json.loads(requete.content))
        code = self.codes.pop(0) if len(self.codes) > 1 else self.codes[0]
        if code == 429:
            return httpx.Response(429, json={"retry_after": self.retry_after})
        return httpx.Response(code)

    def transport(self):
        return httpx.MockTransport(self)


def test_message_de_panne():
    message = notification.message_discord(alerte())
    assert message["title"] == "🔴 Panne : Site 1"
    assert message["color"] == notification.ROUGE
    assert message["fields"] == [{"name": "Cause", "value": "code HTTP 503"}]
    assert message["timestamp"] == DEBUT.isoformat()


def test_message_de_retablissement():
    message = notification.message_discord(alerte(RETABLISSEMENT))
    assert message["title"] == "🟢 Rétabli : Site 1"
    assert message["color"] == notification.VERT
    assert message["fields"][0] == {"name": "Durée de la panne", "value": "12 min"}


def test_une_cause_trop_longue_est_tronquee():
    message = notification.message_discord(alerte(cause="x" * 5000))
    assert len(message["fields"][0]["value"]) == notification.MAX_TEXTE_CHAMP


def test_envoi_reussi():
    discord = FauxDiscord(204)
    envoyees, erreurs = notification.envoyer_discord(WEBHOOK, [alerte()], discord.transport())
    assert len(envoyees) == 1
    assert erreurs == []
    [corps] = discord.recus
    assert corps["username"] == "Vigie"
    assert corps["allowed_mentions"] == {"parse": []}  # jamais de @everyone
    assert len(corps["embeds"]) == 1


def test_les_alertes_partent_par_paquets_de_dix():
    discord = FauxDiscord(204)
    lot = [alerte(numero=numero) for numero in range(23)]
    envoyees, _ = notification.envoyer_discord(WEBHOOK, lot, discord.transport())
    assert len(envoyees) == 23
    assert [len(corps["embeds"]) for corps in discord.recus] == [10, 10, 3]


def test_trop_d_envois_on_patiente_puis_on_reessaie():
    discord = FauxDiscord(429, 204)
    envoyees, erreurs = notification.envoyer_discord(WEBHOOK, [alerte()], discord.transport())
    assert len(envoyees) == 1
    assert erreurs == []
    assert len(discord.recus) == 2


def test_trop_d_envois_deux_fois_l_alerte_est_reportee():
    discord = FauxDiscord(429, 429)
    envoyees, erreurs = notification.envoyer_discord(WEBHOOK, [alerte()], discord.transport())
    assert envoyees == []
    assert "429" in erreurs[0]


def test_un_refus_arrete_l_envoi_sans_reveler_l_adresse_secrete():
    discord = FauxDiscord(500)
    lot = [alerte(numero=numero) for numero in range(15)]
    envoyees, erreurs = notification.envoyer_discord(WEBHOOK, lot, discord.transport())
    assert envoyees == []
    assert erreurs == ["Discord a refusé l'alerte (code 500)"]
    assert "jeton-secret" not in erreurs[0]


def test_discord_injoignable_sans_reveler_l_adresse_secrete():
    def injoignable(requete):
        raise httpx.ConnectError(f"impossible de joindre {requete.url}", request=requete)

    envoyees, erreurs = notification.envoyer_discord(
        WEBHOOK, [alerte()], httpx.MockTransport(injoignable)
    )
    assert envoyees == []
    assert erreurs == ["Discord injoignable (ConnectError)"]


@pytest.mark.parametrize("corps", [b"pas du json", b"[]"])
def test_une_reponse_429_mal_formee_ne_fait_pas_planter(corps, monkeypatch):
    attentes = []
    monkeypatch.setattr(notification.time, "sleep", attentes.append)
    reponses = [httpx.Response(429, content=corps), httpx.Response(204)]
    transport = httpx.MockTransport(lambda requete: reponses.pop(0))

    envoyees, erreurs = notification.envoyer_discord(WEBHOOK, [alerte()], transport)
    assert len(envoyees) == 1
    assert attentes == [1.0]
