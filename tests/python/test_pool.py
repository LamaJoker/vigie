"""Tests du pool de connexions de l'API (lot 8.3).

Avant ce lot, l'API ouvrait une connexion à la base par requête. Avec un pool, elle en
garde quelques-unes ouvertes et les prête aux requêtes : moins d'attente, et un nombre
de connexions borné quelle que soit la charge.
"""

import socket
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager

import httpx
import psycopg
import uvicorn
from fastapi.testclient import TestClient
from outils import resultat
from psycopg import sql

from vigie import base
from vigie.api import creer_app
from vigie.config import Configuration, Site

A = "https://a.test"
CONFIG = Configuration(sites=(Site("Site A", A),))
BASE_INJOIGNABLE = "postgresql://vigie@/aucune?host=/dossier/inexistant&port=1"
NOM_API = "vigie-api"  # nom des connexions de l'API, visible dans pg_stat_activity


def connexions_api(url: str) -> int:
    with psycopg.connect(url) as conn:
        return conn.execute(
            "SELECT count(*) FROM pg_stat_activity WHERE application_name = %s", (NOM_API,)
        ).fetchone()[0]


def attendre(condition, delai: float = 5.0) -> bool:
    fin = time.monotonic() + delai
    while time.monotonic() < fin:
        if condition():
            return True
        time.sleep(0.05)
    return condition()


@contextmanager
def serveur_uvicorn(app):
    """Lance l'application dans un vrai serveur web, sur un port libre."""
    prise = socket.socket()
    prise.bind(("127.0.0.1", 0))
    serveur = uvicorn.Server(uvicorn.Config(app, log_level="warning"))
    fil = threading.Thread(target=serveur.run, kwargs={"sockets": [prise]}, daemon=True)
    fil.start()
    assert attendre(lambda: serveur.started, 10), "le serveur ne démarre pas"
    try:
        yield f"http://127.0.0.1:{prise.getsockname()[1]}"
    finally:
        serveur.should_exit = True
        fil.join(10)
        prise.close()


def test_le_pool_s_ouvre_et_se_ferme_avec_l_application(base_vide):
    app = creer_app(CONFIG, base_vide)
    with TestClient(app) as client:
        assert client.get("/sante").status_code == 200
        assert connexions_api(base_vide) >= 1
    assert app.state.pool.closed
    assert attendre(lambda: connexions_api(base_vide) == 0)


def test_les_requetes_reutilisent_la_meme_connexion(base_vide):
    app = creer_app(CONFIG, base_vide)
    with TestClient(app) as client:
        app.state.pool.wait(5)  # la première connexion est prête
        for _ in range(20):
            assert client.get("/api/sites").status_code == 200
        assert connexions_api(base_vide) == 1


def test_50_requetes_simultanees_restent_dans_la_taille_du_pool(base_vide, monkeypatch):
    with base.connecter(base_vide) as conn:
        base.enregistrer(conn, [resultat(A)])
    # Chaque requête garde sa connexion 0,1 s : sans pool, 50 requêtes simultanées
    # ouvriraient des dizaines de connexions en même temps.
    vraie_lecture = base.etats

    def lecture_lente(*arguments, **options):
        time.sleep(0.1)
        return vraie_lecture(*arguments, **options)

    monkeypatch.setattr(base, "etats", lecture_lente)
    app = creer_app(CONFIG, base_vide, taille_pool=5, attente=20)

    maximum = 0
    fini = threading.Event()

    def observer() -> None:
        nonlocal maximum
        with psycopg.connect(base_vide, autocommit=True) as conn:
            while not fini.is_set():
                nombre = conn.execute(
                    "SELECT count(*) FROM pg_stat_activity WHERE application_name = %s",
                    (NOM_API,),
                ).fetchone()[0]
                maximum = max(maximum, nombre)
                time.sleep(0.005)

    with serveur_uvicorn(app) as adresse:
        observateur = threading.Thread(target=observer)
        observateur.start()
        try:
            with httpx.Client(base_url=adresse, timeout=30) as client, ThreadPoolExecutor(50) as ex:
                codes = list(ex.map(lambda _: client.get("/api/sites").status_code, range(50)))
        finally:
            fini.set()
            observateur.join(10)

    assert codes == [200] * 50
    assert 2 <= maximum <= 5, f"{maximum} connexions ouvertes en même temps"


def test_des_connexions_coupees_sont_remplacees_sans_erreur(base_vide):
    # Comme après un redémarrage de la base : toutes les connexions du pool sont mortes.
    # Cas trouvé par l'essai Docker du 16/11 : avec 5 connexions mortes en réserve, la
    # requête les essayait une à une en patientant entre chaque, et finissait en 503.
    app = creer_app(CONFIG, base_vide)
    with TestClient(app) as client:
        pool = app.state.pool
        connexions = [pool.getconn() for _ in range(5)]  # le pool monte à 5 connexions...
        for connexion in connexions:
            pool.putconn(connexion)  # ...qui attendent toutes en réserve
        assert connexions_api(base_vide) == 5
        with psycopg.connect(base_vide, autocommit=True) as admin:
            admin.execute(
                "SELECT pg_terminate_backend(pid) FROM pg_stat_activity"
                " WHERE application_name = %s",
                (NOM_API,),
            )
        assert attendre(lambda: connexions_api(base_vide) == 0)

        assert client.get("/api/sites").status_code == 200
        assert client.get("/sante").status_code == 200


def test_l_api_repond_des_que_la_base_revient(postgres):
    # Cas trouvé par l'essai Docker du 16/11 : pendant une panne, le pool espace ses essais
    # de reconnexion (1 s, 2 s, 4 s, 8 s...). Une fois la base revenue, l'API restait en
    # erreur jusqu'au prochain essai, parfois plusieurs minutes plus tard.
    nom = f"absente_{uuid.uuid4().hex[:8]}"
    url = postgres.replace("/vigie_test?", f"/{nom}?")
    try:
        with TestClient(creer_app(CONFIG, url, attente=1)) as client:
            assert client.get("/sante").status_code == 503  # la base n'existe pas encore
            time.sleep(3)  # la panne dure : les essais de reconnexion s'espacent
            with psycopg.connect(postgres, autocommit=True) as admin:
                admin.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(nom)))

            assert client.get("/sante").status_code == 200
    finally:
        with psycopg.connect(postgres, autocommit=True) as admin:
            admin.execute(
                sql.SQL("DROP DATABASE IF EXISTS {} WITH (FORCE)").format(sql.Identifier(nom))
            )


def test_base_injoignable_reponse_503_rapide():
    app = creer_app(CONFIG, BASE_INJOIGNABLE, attente=0.5)
    with TestClient(app) as client:
        debut = time.monotonic()
        sante = client.get("/sante")
        sites = client.get("/api/sites")
        duree = time.monotonic() - debut
    assert sante.status_code == 503
    assert sante.json()["base"] == "injoignable"
    assert sites.status_code == 503
    assert "injoignable" in sites.json()["detail"]
    assert duree < 5
