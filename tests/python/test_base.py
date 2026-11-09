"""Tests du stockage PostgreSQL, sur une vraie base jetable."""

from dataclasses import replace
from datetime import timedelta

import psycopg
import pytest
from outils import resultat

from vigie import base
from vigie.config import Site

A = "https://a.test"
B = "https://b.test"
SITES = (Site("A", A), Site("B", B))


@pytest.fixture
def conn(base_vide):
    with base.connecter(base_vide) as connexion:
        yield connexion


def test_initialiser_peut_etre_rejoue(conn):
    base.initialiser(conn)
    base.initialiser(conn)
    assert conn.execute("SELECT count(*) AS n FROM sondes").fetchone()["n"] == 0


def test_enregistrer_renvoie_le_nombre_de_lignes(conn):
    assert base.enregistrer(conn, [resultat(A), resultat(B)]) == 2


def test_le_dernier_resultat_l_emporte(conn):
    base.enregistrer(
        conn,
        [
            resultat(A, "DOWN", 503, il_y_a=timedelta(minutes=10)),
            resultat(A, "UP", 200, il_y_a=timedelta(minutes=1)),
        ],
    )
    [etat_a, _] = base.etats(conn, SITES)
    assert etat_a.etat == "UP"
    assert etat_a.code == 200


def test_un_site_sans_mesure_a_un_etat_inconnu(conn):
    base.enregistrer(conn, [resultat(A)])
    [_, etat_b] = base.etats(conn, SITES)
    assert etat_b.etat is None
    assert etat_b.disponibilite is None
    assert etat_b.mesures == 0


def test_les_etats_suivent_l_ordre_des_sites(conn):
    base.enregistrer(conn, [resultat(B), resultat(A)])
    assert [etat.url for etat in base.etats(conn, SITES)] == [A, B]


def test_disponibilite_sur_les_dernieres_24_heures(conn):
    base.enregistrer(
        conn,
        [
            resultat(A, "UP", il_y_a=timedelta(hours=1)),
            resultat(A, "UP", il_y_a=timedelta(hours=2)),
            resultat(A, "UP", il_y_a=timedelta(hours=3)),
            resultat(A, "DOWN", None, il_y_a=timedelta(hours=4)),
            # trop ancienne : ne compte pas dans la disponibilité
            resultat(A, "DOWN", None, il_y_a=timedelta(hours=30)),
        ],
    )
    [etat_a, _] = base.etats(conn, SITES)
    assert etat_a.disponibilite == pytest.approx(0.75)
    assert etat_a.mesures == 4


def test_historique_du_plus_recent_au_plus_ancien(conn):
    base.enregistrer(
        conn,
        [
            resultat(A, code=200 + minutes, il_y_a=timedelta(minutes=minutes))
            for minutes in range(5)
        ],
    )
    lignes = base.historique(conn, A, limite=3)
    assert [ligne["code"] for ligne in lignes] == [200, 201, 202]


def test_la_base_refuse_un_etat_invalide(conn):
    # La contrainte CHECK du schéma protège les données, même contre un bug du code.
    with pytest.raises(psycopg.errors.CheckViolation):
        base.enregistrer(conn, [replace(resultat(A), etat="PEUT-ETRE")])


def test_la_base_refuse_un_code_http_impossible(conn):
    with pytest.raises(psycopg.errors.CheckViolation):
        base.enregistrer(conn, [resultat(A, code=999)])
