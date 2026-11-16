"""Migrations du schéma de la base : un petit migrateur maison.

Chaque fichier de src/vigie/migrations/ (« 0001_initial.sql », « 0002_... ») fait évoluer
le schéma d'une étape. La table « migrations » de la base retient celles qui sont déjà
appliquées, avec l'empreinte de leur contenu. « vigie migrer » applique les autres, dans
l'ordre, chacune dans sa propre transaction.

Règle d'or : une migration appliquée ne se modifie plus. Pour changer le schéma, on en
écrit une nouvelle. Le migrateur refuse de continuer s'il voit qu'un fichier déjà
appliqué a changé.

Pourquoi un migrateur maison plutôt qu'Alembic : voir docs/decisions/0006.
"""

import hashlib
import re
from collections.abc import Sequence
from dataclasses import dataclass
from importlib import resources
from importlib.resources.abc import Traversable
from pathlib import Path

import psycopg
from psycopg.rows import tuple_row

# Clé du verrou consultatif (« advisory lock ») pris pendant les migrations. C'est un
# nombre choisi une fois pour toutes, le même pour tous les lancements : « vigi » en ASCII.
CLE_VERROU = 0x76696769
NOM_FICHIER = re.compile(r"(\d{4})_[a-z0-9_]+\.sql")

TABLE_MIGRATIONS = """
CREATE TABLE IF NOT EXISTS migrations (
    version    INTEGER     PRIMARY KEY,
    nom        TEXT        NOT NULL,
    empreinte  TEXT        NOT NULL,  -- SHA-256 du fichier, pour repérer une modification
    appliquee  TIMESTAMPTZ NOT NULL DEFAULT now()
)
"""


class ErreurMigration(Exception):
    """Les migrations ne peuvent pas être appliquées sans risque."""


@dataclass(frozen=True)
class Migration:
    version: int
    nom: str  # nom du fichier sans « .sql », par exemple « 0001_initial »
    sql: str

    @property
    def empreinte(self) -> str:
        return hashlib.sha256(self.sql.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class Bilan:
    appliquees: list[Migration]  # migrations appliquées par ce lancement
    version: int  # version de la base à la fin : numéro de la dernière migration
    inconnues: list[int]  # versions présentes en base mais absentes du code


def disponibles(dossier: Traversable | Path | None = None) -> list[Migration]:
    """Les migrations fournies avec Vigie, dans l'ordre. Vérifie leur numérotation."""
    if dossier is None:
        dossier = resources.files("vigie").joinpath("migrations")
    migrations = []
    for fichier in dossier.iterdir():
        if not fichier.name.endswith(".sql"):
            continue
        correspondance = NOM_FICHIER.fullmatch(fichier.name)
        if not correspondance:
            raise ErreurMigration(
                f"nom de migration invalide : {fichier.name} (attendu : 0001_nom_en_minuscules.sql)"
            )
        migrations.append(
            Migration(
                version=int(correspondance[1]),
                nom=fichier.name.removesuffix(".sql"),
                sql=fichier.read_text(encoding="utf-8"),
            )
        )
    migrations.sort(key=lambda migration: (migration.version, migration.nom))
    versions = [migration.version for migration in migrations]
    if versions != list(range(1, len(migrations) + 1)):
        raise ErreurMigration(
            "numérotation des migrations : 1, 2, 3... attendu sans trou ni doublon,"
            f" trouvé {versions}"
        )
    return migrations


def migrer(conn: psycopg.Connection, migrations: Sequence[Migration] | None = None) -> Bilan:
    """Applique les migrations qui manquent à la base. Peut être relancé sans risque.

    Plusieurs lancements simultanés (plusieurs conteneurs qui démarrent en même temps)
    ne se marchent pas dessus : le premier prend un verrou, les autres l'attendent, puis
    constatent qu'il ne reste rien à faire.
    """
    if migrations is None:
        migrations = disponibles()
    autocommit = conn.autocommit
    # En mode autocommit, chaque « with conn.transaction() » ouvre une vraie transaction.
    # Sinon, ce ne serait qu'un point de sauvegarde dans une seule grande transaction.
    conn.autocommit = True
    try:
        # Verrou consultatif : un verrou nommé par un nombre, que PostgreSQL ne pose sur
        # aucune table. Il est lié à la connexion : si le programme meurt, il est rendu.
        conn.execute("SELECT pg_advisory_lock(%s)", (CLE_VERROU,))
        try:
            return _appliquer(conn, migrations)
        finally:
            if not conn.broken:
                conn.execute("SELECT pg_advisory_unlock(%s)", (CLE_VERROU,))
    finally:
        if not conn.closed:
            conn.autocommit = autocommit


def _appliquer(conn: psycopg.Connection, migrations: Sequence[Migration]) -> Bilan:
    conn.execute(TABLE_MIGRATIONS)
    with conn.cursor(row_factory=tuple_row) as curseur:
        # version -> empreinte des migrations déjà appliquées
        deja = dict(curseur.execute("SELECT version, empreinte FROM migrations").fetchall())

    for migration in migrations:
        if migration.version in deja and deja[migration.version] != migration.empreinte:
            raise ErreurMigration(
                f"la migration {migration.nom} a été modifiée après avoir été appliquée."
                " Une migration appliquée ne se modifie pas : il faut en écrire une nouvelle"
            )

    appliquees = []
    for migration in migrations:
        if migration.version in deja:
            continue
        try:
            with conn.transaction():
                conn.execute(migration.sql)
                conn.execute(
                    "INSERT INTO migrations (version, nom, empreinte) VALUES (%s, %s, %s)",
                    (migration.version, migration.nom, migration.empreinte),
                )
        except psycopg.Error as erreur:
            raise ErreurMigration(
                f"la migration {migration.nom} a échoué et a été annulée : {erreur}"
            ) from erreur
        appliquees.append(migration)

    connues = {migration.version for migration in migrations}
    return Bilan(
        appliquees=appliquees,
        version=max([*deja, *connues], default=0),
        inconnues=sorted(set(deja) - connues),
    )
