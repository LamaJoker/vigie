"""Petit serveur HTTP local pour tester la sonde sans dépendre d'Internet.

Utilisation : python3 serveur_test.py PORT

  /200, /503, /404...  répond avec ce code HTTP
  /lent                attend 5 secondes avant de répondre 200
"""

import http.server
import sys
import time


class Gestionnaire(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        chemin = self.path.strip("/")
        if chemin == "lent":
            time.sleep(5)
            code = 200
        elif chemin.isdigit():
            code = int(chemin)
        else:
            code = 404
        try:
            self.send_response(code)
            self.send_header("Content-Length", "0")
            self.end_headers()
        except (BrokenPipeError, ConnectionResetError):
            pass  # le client a abandonné (cas du test de délai dépassé)

    def log_message(self, format, *args):
        pass  # pas de journal : les tests restent lisibles


if __name__ == "__main__":
    port = int(sys.argv[1])
    http.server.ThreadingHTTPServer(("127.0.0.1", port), Gestionnaire).serve_forever()
