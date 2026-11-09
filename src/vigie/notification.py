"""Envoi des alertes sur Discord, par un webhook.

Un webhook Discord est une adresse secrète : quiconque la connaît peut écrire dans
le salon. Elle vient donc de la variable d'environnement VIGIE_DISCORD_WEBHOOK, et
ce module ne l'affiche jamais, même dans les messages d'erreur.
"""

import time
from collections.abc import Sequence
from typing import Any

import httpx

from vigie.alertes import PANNE, Alerte, formater_duree

ROUGE = 0xD92D20
VERT = 0x1F7A4D
MAX_ALERTES_PAR_MESSAGE = 10  # limite de Discord : 10 « embeds » par message
MAX_TEXTE_CHAMP = 1024  # limite de Discord pour la valeur d'un champ
ATTENTE_MAX = 5.0  # secondes d'attente au plus quand Discord demande de patienter


class ErreurNotification(Exception):
    """L'alerte n'a pas pu être envoyée."""


def _tronquer(texte: str) -> str:
    return texte if len(texte) <= MAX_TEXTE_CHAMP else texte[: MAX_TEXTE_CHAMP - 1] + "…"


def message_discord(alerte: Alerte) -> dict[str, Any]:
    """Transforme une alerte en « embed » Discord (carte colorée)."""
    cause = {"name": "Cause", "value": _tronquer(alerte.cause or "inconnue")}
    if alerte.type == PANNE:
        titre, couleur, date = f"🔴 Panne : {alerte.nom}", ROUGE, alerte.debut
        champs = [cause]
    else:
        titre, couleur, date = f"🟢 Rétabli : {alerte.nom}", VERT, alerte.fin or alerte.debut
        champs = [{"name": "Durée de la panne", "value": formater_duree(alerte.duree)}, cause]
    return {
        "title": titre,
        "url": alerte.url,
        "description": alerte.url,
        "color": couleur,
        "timestamp": date.isoformat(),
        "fields": champs,
    }


def _poster(client: httpx.Client, webhook: str, corps: dict[str, Any]) -> None:
    for tentative in (1, 2):
        try:
            reponse = client.post(webhook, json=corps)
        except httpx.HTTPError as exc:
            # Seulement le type d'erreur : le message d'httpx contient l'adresse secrète.
            raise ErreurNotification(f"Discord injoignable ({type(exc).__name__})") from None

        if reponse.status_code == 429 and tentative == 1:
            # Trop d'envois : Discord indique combien de secondes patienter.
            try:
                attente = float(reponse.json().get("retry_after", 1))
            except (ValueError, AttributeError):
                attente = 1.0
            time.sleep(min(max(attente, 0), ATTENTE_MAX))
            continue
        if reponse.is_success:
            return
        raise ErreurNotification(f"Discord a refusé l'alerte (code {reponse.status_code})")


def envoyer_discord(
    webhook: str,
    alertes: Sequence[Alerte],
    transport: httpx.BaseTransport | None = None,
) -> tuple[list[Alerte], list[str]]:
    """Envoie les alertes par paquets de 10.

    Renvoie les alertes bien parties et les erreurs rencontrées. À la première erreur,
    on s'arrête : les alertes restantes seront retentées au passage suivant.
    """
    envoyees: list[Alerte] = []
    with httpx.Client(transport=transport, timeout=10) as client:
        for debut in range(0, len(alertes), MAX_ALERTES_PAR_MESSAGE):
            paquet = alertes[debut : debut + MAX_ALERTES_PAR_MESSAGE]
            corps = {
                "username": "Vigie",
                # Aucune mention (@everyone...) ne doit partir d'un texte de site ou d'erreur.
                "allowed_mentions": {"parse": []},
                "embeds": [message_discord(alerte) for alerte in paquet],
            }
            try:
                _poster(client, webhook, corps)
            except ErreurNotification as erreur:
                return envoyees, [str(erreur)]
            envoyees.extend(paquet)
    return envoyees, []
