"""Tests des incidents, sur une vraie base jetable."""

from datetime import datetime, timedelta

import psycopg
import pytest
from outils import resultat

from vigie import alertes, base
from vigie.alertes import PANNE, RETABLISSEMENT, formater_duree

A = "https://a.test"


@pytest.fixture
def conn(base_vide):
    with base.connecter(base_vide) as connexion:
        yield connexion


def passage(conn, *resultats, echecs_avant_alerte=2):
    """Simule un passage de sonde : enregistrement, puis mise à jour des incidents."""
    base.enregistrer(conn, resultats)
    alertes.mettre_a_jour_incidents(conn, resultats, echecs_avant_alerte)


def panne(minutes):
    return resultat(A, "DOWN", 503, il_y_a=timedelta(minutes=minutes))


def retour(minutes):
    return resultat(A, "UP", 200, il_y_a=timedelta(minutes=minutes))


def incidents(conn):
    return conn.execute("SELECT * FROM incidents ORDER BY id").fetchall()


def test_un_echec_isole_n_ouvre_pas_d_incident(conn):
    passage(conn, panne(10))
    assert incidents(conn) == []


def test_un_echec_entre_deux_succes_n_ouvre_pas_d_incident(conn):
    passage(conn, panne(10))
    passage(conn, retour(5))
    passage(conn, panne(1))
    assert incidents(conn) == []


def test_deux_echecs_consecutifs_ouvrent_un_incident(conn):
    premier = panne(10)
    passage(conn, premier)
    passage(conn, panne(5))
    [incident] = incidents(conn)
    assert incident["fin"] is None
    assert incident["cause"] == "code HTTP 503"
    # la panne commence au premier échec, pas au moment où on la confirme
    assert incident["debut"] == datetime.fromisoformat(premier.date)


def test_seuil_de_un_echec(conn):
    passage(conn, panne(1), echecs_avant_alerte=1)
    assert len(incidents(conn)) == 1


def test_une_panne_qui_dure_reste_un_seul_incident(conn):
    for minutes in (25, 20, 15, 10, 5):
        passage(conn, panne(minutes))
    assert len(incidents(conn)) == 1


def test_le_retour_du_site_ferme_l_incident(conn):
    passage(conn, panne(20))
    passage(conn, panne(15))
    revenu = retour(5)
    passage(conn, revenu)
    [incident] = incidents(conn)
    assert incident["fin"] == datetime.fromisoformat(revenu.date)


def test_une_nouvelle_panne_ouvre_un_nouvel_incident(conn):
    passage(conn, panne(40))
    passage(conn, panne(35))
    passage(conn, retour(30))
    passage(conn, panne(10))
    passage(conn, panne(5))
    assert [incident["fin"] is None for incident in incidents(conn)] == [False, True]


def test_la_cause_vient_du_message_d_erreur(conn):
    muet = resultat(A, "DOWN", None, erreur="pas de réponse en 10 s")
    passage(conn, muet, echecs_avant_alerte=1)
    assert incidents(conn)[0]["cause"] == "pas de réponse en 10 s"


def test_alertes_en_attente_puis_envoyees(conn):
    passage(conn, panne(10))
    passage(conn, panne(5))
    [alerte] = alertes.alertes_en_attente(conn)
    assert alerte.type == PANNE

    alertes.marquer_envoyee(conn, alerte)
    assert alertes.alertes_en_attente(conn) == []

    passage(conn, retour(1))
    [alerte] = alertes.alertes_en_attente(conn)
    assert alerte.type == RETABLISSEMENT
    assert alerte.duree == timedelta(minutes=9)

    alertes.marquer_envoyee(conn, alerte)
    assert alertes.alertes_en_attente(conn) == []


def test_panne_et_retour_avant_tout_envoi_donnent_deux_alertes_dans_l_ordre(conn):
    passage(conn, panne(10))
    passage(conn, panne(5))
    passage(conn, retour(1))
    assert [alerte.type for alerte in alertes.alertes_en_attente(conn)] == [PANNE, RETABLISSEMENT]


def test_la_base_interdit_deux_incidents_ouverts_pour_un_site(conn):
    requete = "INSERT INTO incidents (nom, url, debut) VALUES ('A', %s, now())"
    conn.execute(requete, (A,))
    with pytest.raises(psycopg.errors.UniqueViolation):
        conn.execute(requete, (A,))


def test_incidents_recents(conn):
    passage(conn, panne(40))
    passage(conn, panne(35))
    passage(conn, retour(30))
    passage(conn, panne(10))
    passage(conn, panne(5))
    [recent, ancien] = alertes.incidents_recents(conn, [A])
    assert recent["en_cours"] is True
    assert recent["duree"] == "en cours"
    assert ancien["en_cours"] is False
    assert ancien["duree"] == "10 min"
    assert len(alertes.incidents_recents(conn, [A], limite=1)) == 1


def test_un_site_qui_n_est_plus_surveille_disparait_des_incidents(conn):
    passage(conn, panne(1), echecs_avant_alerte=1)
    assert alertes.incidents_recents(conn, ["https://autre.test"]) == []


def test_l_incident_d_un_site_retire_est_ferme_sans_alerte(conn):
    passage(conn, panne(1), echecs_avant_alerte=1)  # incident ouvert, alerte de panne en attente
    assert len(alertes.alertes_en_attente(conn)) == 1

    assert alertes.fermer_incidents_retires(conn, ["https://autre.test"]) == 1

    [incident] = incidents(conn)
    assert incident["fin"] is not None
    assert incident["motif_fin"] == alertes.MOTIF_SITE_RETIRE
    assert alertes.alertes_en_attente(conn) == []  # ni panne ni rétablissement ne partira


def test_les_incidents_des_sites_surveilles_restent_ouverts(conn):
    passage(conn, panne(1), echecs_avant_alerte=1)
    assert alertes.fermer_incidents_retires(conn, [A]) == 0
    assert incidents(conn)[0]["fin"] is None


def test_le_schema_met_a_niveau_une_base_d_avant_le_lot_8_1(conn):
    # Une base créée avant le lot 8.1 n'a pas la colonne motif_fin : rejouer le schéma l'ajoute.
    conn.execute("ALTER TABLE incidents DROP COLUMN motif_fin")
    conn.commit()
    base.initialiser(conn)
    passage(conn, panne(1), echecs_avant_alerte=1)
    assert alertes.fermer_incidents_retires(conn, []) == 1


@pytest.mark.parametrize(
    ("secondes", "texte"),
    [(0, "0 s"), (45, "45 s"), (600, "10 min"), (3725, "1 h 2 min 5 s"), (-3, "0 s")],
)
def test_formater_duree(secondes, texte):
    assert formater_duree(timedelta(seconds=secondes)) == texte


def test_formater_duree_en_cours():
    assert formater_duree(None) == "en cours"
