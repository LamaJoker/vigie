"""API web et page de statut de Vigie (FastAPI).

GET /                          page de statut lisible par un humain
GET /api/sites                 état de chaque site, en JSON
GET /api/sites/historique      derniers résultats d'un site (?url=...&limite=...)
GET /api/incidents             derniers incidents (pannes)
GET /sante                     l'application et sa base répondent-elles ?
GET /docs                      documentation interactive de l'API (générée par FastAPI)
"""

from datetime import datetime
from importlib import resources

import psycopg
from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates

from vigie import __version__, alertes, base
from vigie.config import Configuration


def creer_app(config: Configuration, database_url: str) -> FastAPI:
    app = FastAPI(
        title="Vigie",
        version=__version__,
        description="Surveillance de sites web : état, temps de réponse, disponibilité.",
    )
    modeles = Jinja2Templates(directory=str(resources.files("vigie").joinpath("modeles")))
    urls_connues = {site.url for site in config.sites}
    urls_surveillees = [site.url for site in config.sites]

    def lire_etats() -> list[base.EtatSite]:
        with base.connecter(database_url) as conn:
            return base.etats(conn, config.sites)

    @app.exception_handler(psycopg.OperationalError)
    def base_injoignable(request: Request, erreur: psycopg.OperationalError) -> JSONResponse:
        return JSONResponse({"detail": "base de données injoignable"}, status_code=503)

    @app.get("/sante", summary="Vérifier que l'application et sa base répondent")
    def sante() -> JSONResponse:
        try:
            with base.connecter(database_url) as conn:
                base.verifier(conn)
        except psycopg.OperationalError:
            return JSONResponse({"statut": "erreur", "base": "injoignable"}, status_code=503)
        return JSONResponse({"statut": "ok", "base": "ok"})

    @app.get("/api/sites", summary="État actuel de chaque site")
    def api_sites() -> list[base.EtatSite]:
        return lire_etats()

    @app.get("/api/sites/historique", summary="Derniers résultats d'un site")
    def api_historique(url: str, limite: int = Query(50, ge=1, le=1000)) -> list[dict]:
        if url not in urls_connues:
            raise HTTPException(status_code=404, detail="site inconnu")
        with base.connecter(database_url) as conn:
            return base.historique(conn, url, limite)

    @app.get("/api/incidents", summary="Derniers incidents (pannes), du plus récent au plus ancien")
    def api_incidents(limite: int = Query(20, ge=1, le=200)) -> list[dict]:
        with base.connecter(database_url) as conn:
            return alertes.incidents_recents(conn, urls_surveillees, limite)

    @app.get("/", response_class=HTMLResponse, include_in_schema=False)
    def page_statut(request: Request) -> HTMLResponse:
        with base.connecter(database_url) as conn:
            etats = base.etats(conn, config.sites)
            incidents = alertes.incidents_recents(conn, urls_surveillees, 10)
        return modeles.TemplateResponse(
            request,
            "statut.html",
            {
                "etats": etats,
                "incidents": incidents,
                "en_panne": [etat for etat in etats if etat.etat == "DOWN"],
                "mesures_existent": any(etat.etat is not None for etat in etats),
                "mise_a_jour": datetime.now().astimezone().strftime("%d/%m/%Y à %H:%M:%S"),
            },
        )

    return app
