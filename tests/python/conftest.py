"""Outils partagés par les tests : un vrai petit serveur HTTP local."""

import http.server
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
