# Journal des versions

Toutes les évolutions notables de Vigie. Le format suit [Keep a Changelog](https://keepachangelog.com/fr/1.1.0/), et les numéros de version suivent la [gestion sémantique de version](https://semver.org/lang/fr/).

Les versions 0.1 à 0.5 ont été reconstituées le 10/11/2026 à partir des pull requests : elles n'ont pas d'étiquette Git. La première version publiée avec une étiquette sera la 0.8.0 (lot 8.6).

## [Non publiée]

### Ajouté
- Feuille de route découpée en lots, jalons et tickets GitHub ; décisions d'architecture ; schéma d'architecture ; ce journal des versions ; licence MIT (lot 0, [#8](https://github.com/LamaJoker/vigie/issues/8)).
- Vérification automatique des liens de la documentation, dans `make lint` et dans la CI (lot 0).
- Intégration continue GitHub Actions : style et analyse, tests sur Python 3.12 et 3.14 avec couverture minimale, tests Bash, essai de bout en bout de la pile, publication de l'image sur `ghcr.io` depuis `main` ; cible `make ci` ([PR 7](https://github.com/LamaJoker/vigie/pull/7)).

### Modifié
- Les « semaines » deviennent des « étapes » : `docs/semaines/` devient `docs/etapes/` (lot 0).

## [0.5.0] - 2026-11-09

### Ajouté
- Image Docker en deux étapes, sans root (UID 10001), et pile Docker Compose : base PostgreSQL, création des tables, API, sonde ([PR 6](https://github.com/LamaJoker/vigie/pull/6)).
- Commande `vigie surveiller` : sonde en boucle, arrêt propre sur SIGTERM.
- Essai de bout en bout de la pile (`make tests-docker`) ; analyse du Dockerfile (hadolint).

### Corrigé
- La sonde plantait en boucle quand son dossier de travail n'était pas inscriptible : message clair à la place.

## [0.4.0] - 2026-11-09

### Ajouté
- Incidents : ouverts après N échecs consécutifs, un seul par site (garanti par la base), fermés au retour du site ([PR 5](https://github.com/LamaJoker/vigie/pull/5)).
- Alertes Discord au début et à la fin de chaque incident, renvoyées au passage suivant si elles n'ont pas été reçues ; commande `vigie tester-alerte`.
- Section « Derniers incidents » de la page de statut, `GET /api/incidents`.

## [0.3.0] - 2026-11-09

### Ajouté
- Stockage des mesures dans PostgreSQL, commande `vigie init-db` ([PR 4](https://github.com/LamaJoker/vigie/pull/4)).
- API FastAPI et page de statut, point de contrôle `/sante`.

## [0.2.0] - 2026-11-09

### Ajouté
- Sonde réécrite en Python : configuration TOML validée, sites testés en parallèle, résultats en JSON Lines ([PR 3](https://github.com/LamaJoker/vigie/pull/3)).
- Tests pytest, Makefile, contrôle du style avec ruff.

### Corrigé
- Wikipédia refusait la sonde (code 403) : l'identifiant envoyé contient désormais l'adresse du projet.

## [0.1.0] - 2026-11-09

### Ajouté
- Sonde Bash avec `curl`, journal des résultats, installation d'une tâche cron ([PR 2](https://github.com/LamaJoker/vigie/pull/2)).
- Tests bats et analyse ShellCheck.
