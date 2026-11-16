"""Test des sites : une requête HTTP par site, plusieurs sites en parallèle."""

import asyncio
import logging
import time
from dataclasses import asdict, dataclass
from datetime import datetime
from typing import Any

import httpx

from vigie import __version__
from vigie.config import Configuration, Site

# Un robot poli dit qui il est et comment joindre son auteur : certains sites,
# comme Wikipédia, refusent (code 403) les robots qui ne le font pas.
AGENT = f"vigie/{__version__} (+https://github.com/LamaJoker/vigie; projet de formation DevOps)"

journal = logging.getLogger(__name__)


@dataclass(frozen=True)
class Resultat:
    date: str  # date ISO 8601, avec le fuseau horaire
    nom: str
    url: str
    etat: str  # "UP" ou "DOWN"
    code: int | None  # code HTTP, None quand le site n'a pas répondu
    duree_ms: int
    erreur: str | None  # raison de l'échec quand le site n'a pas répondu

    @property
    def en_ligne(self) -> bool:
        return self.etat == "UP"

    def en_dict(self) -> dict[str, Any]:
        return asdict(self)


def maintenant() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


async def sonder_site(client: httpx.AsyncClient, site: Site, delai: float) -> Resultat:
    """Teste un site. Ne lève jamais d'exception : un échec donne un résultat DOWN."""
    date = maintenant()
    debut = time.perf_counter()
    code: int | None = None
    erreur: str | None = None

    try:
        # Délai TOTAL de la requête, redirections comprises (comme curl --max-time).
        async with asyncio.timeout(delai):
            # Lecture en flux : on garde le code et les en-têtes, puis on ferme la
            # connexion sans télécharger le corps de la page, qui ne sert à rien ici.
            async with client.stream("GET", site.url) as reponse:
                code = reponse.status_code
    except (TimeoutError, httpx.TimeoutException):
        erreur = f"pas de réponse en {delai:g} s"
    except httpx.HTTPError as exc:
        erreur = str(exc) or type(exc).__name__
    except Exception as exc:
        # Filet de sécurité : une erreur imprévue (bug, cas limite d'une bibliothèque)
        # ne doit jamais empêcher de mesurer les autres sites. Le site est noté DOWN,
        # et la trace complète part dans le journal pour qu'on puisse corriger.
        journal.warning("erreur imprévue en testant %s", site.url, exc_info=True)
        erreur = f"erreur interne ({type(exc).__name__})"

    duree_ms = round((time.perf_counter() - debut) * 1000)
    etat = "UP" if code is not None and 200 <= code < 400 else "DOWN"
    return Resultat(date, site.nom, site.url, etat, code, duree_ms, erreur)


async def sonder_tous(
    config: Configuration, transport: httpx.AsyncBaseTransport | None = None
) -> list[Resultat]:
    """Teste tous les sites, au plus `config.paralleles` à la fois.

    Les résultats sont rendus dans l'ordre de la configuration. Le paramètre
    `transport` permet aux tests de simuler les réponses sans réseau.
    """
    limite = asyncio.Semaphore(config.paralleles)

    async with httpx.AsyncClient(
        transport=transport,
        follow_redirects=True,
        timeout=config.delai,
        headers={"User-Agent": AGENT},
    ) as client:

        async def sonder_avec_limite(site: Site) -> Resultat:
            async with limite:
                return await sonder_site(client, site, config.delai)

        return list(await asyncio.gather(*(sonder_avec_limite(site) for site in config.sites)))
