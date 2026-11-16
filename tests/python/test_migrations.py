"""Tests du migrateur de schéma (lot 8.3), sur de vraies bases PostgreSQL jetables.

Chaque test part d'une base neuve (fixture « nouvelle_base ») : vide, ou créée par un
ancien schema.sql conservé dans schemas-historiques/.
"""

import subprocess
import sys
import threading
import time
from pathlib import Path

import psycopg
import pytest

from vigie import base, migrateur
from vigie.cli import main
from vigie.migrateur import ErreurMigration, Migration

HISTORIQUES = Path(__file__).parent / "schemas-historiques"
BASE_INJOIGNABLE = "postgresql://vigie@/aucune?host=/dossier/inexistant&port=1"


def structure(url: str) -> dict[str, list]:
    """Photo du schéma : colonnes, contraintes et index de toutes les tables."""
    with base.connecter(url) as conn:
        return {
            "colonnes": conn.execute(
                "SELECT table_name, ordinal_position, column_name, data_type, is_nullable,"
                " column_default, is_identity FROM information_schema.columns"
                " WHERE table_schema = 'public' ORDER BY table_name, ordinal_position"
            ).fetchall(),
            "contraintes": conn.execute(
                "SELECT conrelid::regclass::text AS table_name, conname,"
                " pg_get_constraintdef(oid) AS definition FROM pg_constraint"
                " WHERE connamespace = 'public'::regnamespace ORDER BY 1, 2"
            ).fetchall(),
            "index": conn.execute(
                "SELECT tablename, indexname, indexdef FROM pg_indexes"
                " WHERE schemaname = 'public' ORDER BY 1, 2"
            ).fetchall(),
        }


def migrer(url: str, migrations=None) -> migrateur.Bilan:
    with base.connecter(url) as conn:
        return migrateur.migrer(conn, migrations)


def migrations_en_base(url: str) -> list[dict]:
    with base.connecter(url) as conn:
        return conn.execute("SELECT * FROM migrations ORDER BY version").fetchall()


def table_existe(url: str, table: str) -> bool:
    with base.connecter(url) as conn:
        return conn.execute("SELECT to_regclass(%s) AS t", (table,)).fetchone()["t"] is not None


# --- Les fichiers de migration ------------------------------------------------------------


def test_les_migrations_fournies_se_suivent_sans_trou():
    migrations = migrateur.disponibles()
    assert [m.version for m in migrations] == list(range(1, len(migrations) + 1))
    assert migrations[0].nom == "0001_initial"
    assert len(migrations) >= 3


def test_une_migration_a_une_empreinte_de_son_contenu():
    un = Migration(1, "0001_a", "SELECT 1;")
    assert un.empreinte == Migration(1, "0001_a", "SELECT 1;").empreinte
    assert un.empreinte != Migration(1, "0001_a", "SELECT 2;").empreinte


def test_un_trou_dans_la_numerotation_est_refuse(tmp_path):
    (tmp_path / "0001_a.sql").write_text("SELECT 1;", encoding="utf-8")
    (tmp_path / "0003_c.sql").write_text("SELECT 1;", encoding="utf-8")
    with pytest.raises(ErreurMigration, match="numérotation"):
        migrateur.disponibles(tmp_path)


def test_un_doublon_dans_la_numerotation_est_refuse(tmp_path):
    (tmp_path / "0001_a.sql").write_text("SELECT 1;", encoding="utf-8")
    (tmp_path / "0001_b.sql").write_text("SELECT 1;", encoding="utf-8")
    with pytest.raises(ErreurMigration, match="numérotation"):
        migrateur.disponibles(tmp_path)


@pytest.mark.parametrize("nom", ["1_a.sql", "0002-tiret.sql", "0002_Majuscule.sql"])
def test_un_nom_de_fichier_mal_forme_est_refuse(tmp_path, nom):
    (tmp_path / "0001_a.sql").write_text("SELECT 1;", encoding="utf-8")
    (tmp_path / nom).write_text("SELECT 1;", encoding="utf-8")
    with pytest.raises(ErreurMigration, match="nom de migration invalide"):
        migrateur.disponibles(tmp_path)


def test_les_autres_fichiers_sont_ignores(tmp_path):
    (tmp_path / "0001_a.sql").write_text("SELECT 1;", encoding="utf-8")
    (tmp_path / "LISEZMOI.md").write_text("notes", encoding="utf-8")
    assert [m.nom for m in migrateur.disponibles(tmp_path)] == ["0001_a"]


# --- Appliquer les migrations ---------------------------------------------------------


def test_une_base_vide_recoit_tout_le_schema(nouvelle_base):
    url = nouvelle_base()
    bilan = migrer(url)
    toutes = migrateur.disponibles()
    assert [m.nom for m in bilan.appliquees] == [m.nom for m in toutes]
    assert bilan.version == len(toutes)
    assert table_existe(url, "sondes") and table_existe(url, "incidents")
    assert [ligne["nom"] for ligne in migrations_en_base(url)] == [m.nom for m in toutes]


def test_relancer_ne_change_rien(nouvelle_base):
    url = nouvelle_base()
    migrer(url)
    avant, journal_avant = structure(url), migrations_en_base(url)

    bilan = migrer(url)

    assert bilan.appliquees == []
    assert bilan.version == len(migrateur.disponibles())
    assert structure(url) == avant
    assert migrations_en_base(url) == journal_avant  # mêmes lignes, mêmes dates


@pytest.mark.parametrize("ancien_schema", ["v0.4.sql", "v0.5.sql", "lot-8.1.sql"])
def test_une_base_creee_par_l_ancien_schema_arrive_au_meme_schema(nouvelle_base, ancien_schema):
    reference = nouvelle_base()
    migrer(reference)

    ancienne = nouvelle_base()
    with base.connecter(ancienne) as conn:
        conn.execute((HISTORIQUES / ancien_schema).read_text(encoding="utf-8"))
        conn.execute(
            "INSERT INTO sondes (date, nom, url, etat, code, duree_ms)"
            " VALUES (now(), 'A', 'https://a.test', 'UP', 200, 120)"
        )
        conn.commit()

    migrer(ancienne)

    assert structure(ancienne) == structure(reference)
    with base.connecter(ancienne) as conn:  # les données d'avant sont gardées
        assert conn.execute("SELECT count(*) AS n FROM sondes").fetchone()["n"] == 1


def test_migrer_rend_la_connexion_dans_son_mode(nouvelle_base):
    with base.connecter(nouvelle_base()) as conn:
        assert conn.autocommit is False
        migrateur.migrer(conn)
        assert conn.autocommit is False


# --- Plusieurs lancements en même temps ------------------------------------------------


def test_deux_migrer_simultanes_reussissent_tous_les_deux(nouvelle_base):
    url = nouvelle_base()
    depart = threading.Barrier(4)
    bilans, erreurs = [], []

    def lancer():
        try:
            with base.connecter(url) as conn:
                depart.wait()
                bilans.append(migrateur.migrer(conn))
        except Exception as erreur:  # on veut voir toute erreur, quelle qu'elle soit
            erreurs.append(erreur)

    fils = [threading.Thread(target=lancer) for _ in range(4)]
    for fil in fils:
        fil.start()
    for fil in fils:
        fil.join(30)

    assert erreurs == []
    assert len(bilans) == 4
    # Chaque migration n'a été appliquée qu'une fois, par un seul des lancements.
    appliquees = [m.nom for bilan in bilans for m in bilan.appliquees]
    assert sorted(appliquees) == [m.nom for m in migrateur.disponibles()]
    assert len(migrations_en_base(url)) == len(migrateur.disponibles())


def test_le_verrou_fait_attendre_le_second_lancement(nouvelle_base):
    url = nouvelle_base()
    with psycopg.connect(url, autocommit=True) as autre:
        # Un autre lancement tient le verrou.
        autre.execute("SELECT pg_advisory_lock(%s)", (migrateur.CLE_VERROU,))
        fil = threading.Thread(target=migrer, args=(url,))
        fil.start()
        time.sleep(0.5)
        assert fil.is_alive()  # il attend...
        assert not table_existe(url, "migrations")  # ...sans avoir rien touché
        autre.execute("SELECT pg_advisory_unlock(%s)", (migrateur.CLE_VERROU,))
        fil.join(10)
    assert not fil.is_alive()
    assert table_existe(url, "sondes")


def test_deux_vigie_migrer_lances_en_meme_temps(nouvelle_base):
    url = nouvelle_base()
    commande = [sys.executable, "-m", "vigie", "migrer", "--base", url]
    processus = [
        subprocess.Popen(commande, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        for _ in range(2)
    ]
    sorties = [p.communicate(timeout=60) for p in processus]

    assert [p.returncode for p in processus] == [0, 0], sorties
    textes = sorted(sortie for sortie, _ in sorties)
    # L'un a tout appliqué, l'autre a attendu puis trouvé la base à jour.
    assert sum("Migration appliquée" in texte for texte in textes) == 1
    assert sum("déjà à jour" in texte for texte in textes) == 1


# --- Les cas d'erreur -----------------------------------------------------------------


def test_une_migration_qui_echoue_est_annulee_en_entier(nouvelle_base):
    url = nouvelle_base()
    fournies = migrateur.disponibles()
    cassee = Migration(
        len(fournies) + 1,
        f"{len(fournies) + 1:04d}_cassee",
        "CREATE TABLE essai (x integer); SELECT 1 / 0;",
    )

    with pytest.raises(ErreurMigration, match="cassee"):
        migrer(url, [*fournies, cassee])

    # Les migrations d'avant sont gardées, celle qui a échoué n'a rien laissé...
    assert [ligne["nom"] for ligne in migrations_en_base(url)] == [m.nom for m in fournies]
    assert not table_existe(url, "essai")
    # ...et le verrou est rendu : un nouveau lancement passe tout de suite.
    assert migrer(url).appliquees == []


def test_une_migration_modifiee_apres_application_est_refusee(nouvelle_base):
    url = nouvelle_base()
    migrer(url)
    with base.connecter(url) as conn:
        conn.execute("UPDATE migrations SET empreinte = 'autre' WHERE version = 1")
        conn.commit()

    with pytest.raises(ErreurMigration, match="0001_initial.*modifiée"):
        migrer(url)


def test_une_base_en_avance_sur_le_code_est_signalee(nouvelle_base):
    # Cas d'un retour à une version précédente de Vigie : la base a une migration de plus.
    url = nouvelle_base()
    migrer(url)
    with base.connecter(url) as conn:
        conn.execute("INSERT INTO migrations (version, nom, empreinte) VALUES (99, '0099_x', 'x')")
        conn.commit()

    bilan = migrer(url)

    assert bilan.inconnues == [99]
    assert bilan.version == 99
    assert bilan.appliquees == []


# --- La commande « vigie migrer » ------------------------------------------------------


def test_vigie_migrer(nouvelle_base, capsys):
    url = nouvelle_base()
    assert main(["migrer", "--base", url]) == 0
    sortie = capsys.readouterr().out
    assert "Migration appliquée : 0001_initial" in sortie
    assert f"à jour (version {len(migrateur.disponibles())})" in sortie

    assert main(["migrer", "--base", url]) == 0
    sortie = capsys.readouterr().out
    assert "Migration appliquée" not in sortie
    assert "déjà à jour" in sortie


def test_init_db_reste_un_alias_de_migrer(nouvelle_base, capsys):
    url = nouvelle_base()
    assert main(["init-db", "--base", url]) == 0
    assert "Migration appliquée : 0001_initial" in capsys.readouterr().out
    assert table_existe(url, "sondes")


def test_vigie_migrer_sans_adresse(capsys):
    assert main(["migrer"]) == 2
    assert "VIGIE_DATABASE_URL" in capsys.readouterr().err


def test_vigie_migrer_base_injoignable(capsys):
    assert main(["migrer", "--base", BASE_INJOIGNABLE]) == 2
    assert "migration impossible" in capsys.readouterr().err


def test_vigie_migrer_refuse_une_migration_modifiee(nouvelle_base, capsys):
    url = nouvelle_base()
    migrer(url)
    with base.connecter(url) as conn:
        conn.execute("UPDATE migrations SET empreinte = 'autre' WHERE version = 2")
        conn.commit()

    assert main(["migrer", "--base", url]) == 2
    assert "modifiée" in capsys.readouterr().err


def test_vigie_migrer_signale_une_base_en_avance(nouvelle_base, capsys):
    url = nouvelle_base()
    migrer(url)
    with base.connecter(url) as conn:
        conn.execute("INSERT INTO migrations (version, nom, empreinte) VALUES (99, '0099_x', 'x')")
        conn.commit()

    assert main(["migrer", "--base", url]) == 0
    assert "inconnue" in capsys.readouterr().err
