"""Outils partagés par les tests : un petit serveur HTTP local et une base PostgreSQL jetable."""

import http.server
import shutil
import subprocess
import threading
import time
from collections.abc import Iterator
from pathlib import Path

import pytest


class Gestionnaire(http.server.BaseHTTPRequestHandler):
    """/200, /503... répondent ce code ; /lent attend 3 s ; /redirection renvoie vers /200."""

    def do_GET(self) -> None:
        chemin = self.path.strip("/")
        entetes = {"Content-Length": "0"}
        if chemin == "lent":
            time.sleep(3)
            code = 200
        elif chemin == "redirection":
            code = 302
            entetes["Location"] = "/200"
        elif chemin.isdigit():
            code = int(chemin)
        else:
            code = 404
        try:
            self.send_response(code)
            for nom, valeur in entetes.items():
                self.send_header(nom, valeur)
            self.end_headers()
        except (BrokenPipeError, ConnectionResetError):
            pass  # le client a abandonné (test de délai dépassé)

    def log_message(self, format: str, *args: object) -> None:
        pass


@pytest.fixture(autouse=True)
def environnement_propre(monkeypatch: pytest.MonkeyPatch) -> None:
    """Les variables VIGIE_* de la machine ne doivent pas influencer les tests."""
    for variable in ("VIGIE_CONFIG", "VIGIE_LOG", "VIGIE_DATABASE_URL"):
        monkeypatch.delenv(variable, raising=False)


@pytest.fixture(scope="session")
def serveur() -> Iterator[str]:
    """Démarre le serveur sur un port libre et renvoie son adresse de base."""
    httpd = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Gestionnaire)
    httpd.daemon_threads = True
    fil = threading.Thread(target=httpd.serve_forever, daemon=True)
    fil.start()
    yield f"http://127.0.0.1:{httpd.server_address[1]}"
    httpd.shutdown()
    httpd.server_close()


@pytest.fixture
def ecrire_config(tmp_path: Path):
    """Écrit un fichier de configuration avec les adresses données."""

    def _ecrire(urls: list[str], delai: float = 2, paralleles: int = 10) -> Path:
        lignes = [f"[sonde]\ndelai = {delai}\nparalleles = {paralleles}\n"]
        for numero, url in enumerate(urls, start=1):
            lignes.append(f'[[sites]]\nnom = "site {numero}"\nurl = "{url}"\n')
        chemin = tmp_path / "vigie.toml"
        chemin.write_text("\n".join(lignes), encoding="utf-8")
        return chemin

    return _ecrire


def binaires_postgres() -> Path | None:
    """Dossier des programmes PostgreSQL (initdb, pg_ctl), ou None s'il est absent."""
    versions = sorted(
        Path("/usr/lib/postgresql").glob("*/bin/initdb"), key=lambda p: int(p.parts[-3])
    )
    if versions:
        return versions[-1].parent
    initdb = shutil.which("initdb")
    return Path(initdb).parent if initdb else None


@pytest.fixture(scope="session")
def postgres(tmp_path_factory: pytest.TempPathFactory) -> Iterator[str]:
    """Lance une instance PostgreSQL jetable pour toute la session de tests.

    Elle n'écoute que sur un fichier socket dans un dossier temporaire (aucun port
    réseau ouvert), et elle est détruite à la fin des tests.
    """
    binaires = binaires_postgres()
    if binaires is None:
        pytest.skip("PostgreSQL n'est pas installé (initdb introuvable)")

    dossier = tmp_path_factory.mktemp("pg")
    donnees = dossier / "donnees"
    port = 5499
    subprocess.run(
        [binaires / "initdb", "-D", donnees, "-U", "vigie", "--auth=trust", "-E", "UTF8"],
        check=True,
        capture_output=True,
    )
    options = f"-p {port} -k {dossier} -c listen_addresses=''"
    subprocess.run(
        [
            binaires / "pg_ctl",
            "-D",
            donnees,
            "-l",
            dossier / "pg.log",
            "-o",
            options,
            "-w",
            "start",
        ],
        check=True,
        capture_output=True,
    )
    subprocess.run(
        [binaires / "createdb", "-h", dossier, "-p", str(port), "-U", "vigie", "vigie_test"],
        check=True,
        capture_output=True,
    )
    try:
        yield f"postgresql://vigie@/vigie_test?host={dossier}&port={port}"
    finally:
        subprocess.run(
            [binaires / "pg_ctl", "-D", donnees, "-m", "immediate", "stop"], capture_output=True
        )


@pytest.fixture
def base_vide(postgres: str) -> str:
    """Base avec les tables créées et vidées : chaque test part de zéro."""
    from vigie import base

    with base.connecter(postgres) as conn:
        base.initialiser(conn)
        conn.execute("TRUNCATE sondes")
        conn.commit()
    return postgres
