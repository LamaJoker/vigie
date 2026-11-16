# Journal des versions

Toutes les évolutions notables de Vigie. Le format suit [Keep a Changelog](https://keepachangelog.com/fr/1.1.0/), et les numéros de version suivent la [gestion sémantique de version](https://semver.org/lang/fr/).

Les versions 0.1 à 0.5 ont été reconstituées le 10/11/2026 à partir des pull requests : elles n'ont pas d'étiquette Git. La première version publiée avec une étiquette sera la 0.8.0 (lot 8.6).

## [Non publiée]

### Ajouté
- Feuille de route découpée en lots, jalons et tickets GitHub ; décisions d'architecture ; schéma d'architecture ; ce journal des versions ; licence MIT (lot 0, [#8](https://github.com/LamaJoker/vigie/issues/8)).
- Vérification automatique des liens de la documentation, dans `make lint` et dans la CI (lot 0).
- Intégration continue GitHub Actions : style et analyse, tests sur Python 3.12 et 3.14 avec couverture minimale, tests Bash, essai de bout en bout de la pile, publication de l'image sur `ghcr.io` depuis `main` ; cible `make ci` ([PR 7](https://github.com/LamaJoker/vigie/pull/7)).

- Colonne `motif_fin` des incidents : pourquoi un incident s'est fermé autrement que par le retour du site (lot 8.1).

### Modifié
- Les « semaines » deviennent des « étapes » : `docs/semaines/` devient `docs/etapes/` (lot 0).
- **Le temps de réponse mesuré s'arrête désormais à la réception des en-têtes** : la sonde ne télécharge plus le corps des pages. Les temps baissent d'environ 35 à 45 % sur les gros sites. Ils ne sont donc pas directement comparables à ceux d'avant (lot 8.1, [#9](https://github.com/LamaJoker/vigie/issues/9)).
- `vigie surveiller` survit aux erreurs imprévues d'un passage, mais s'arrête avec le code 1 après 5 erreurs imprévues de suite, pour que Docker ou Kubernetes la relance (lot 8.1).

### Corrigé
- Une adresse au port impossible (`https://example.com:99999`) faisait planter tout le passage : plus aucun site n'était mesuré. Elle est maintenant refusée au chargement de la configuration (lot 8.1).
- Une adresse mal formée (`http://[::1`), un fichier de configuration qui n'est pas en UTF-8 ou un dossier à la place du fichier provoquaient une trace Python au lieu d'un message et du code 2 (lot 8.1).
- Les adresses contenant un espace, un caractère invisible, sans nom d'hôte ou de plus de 2 000 caractères sont refusées au chargement (lot 8.1).
- Une erreur imprévue sur un site faisait échouer tout le passage. Le site est maintenant noté `DOWN` (« erreur interne »), la trace part dans le journal, et les autres sites sont mesurés (lot 8.1).
- Un site retiré de la configuration gardait un incident « en cours » pour toujours, et une alerte encore en attente pour lui finissait par partir. L'incident est maintenant fermé sans alerte (lot 8.1).

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
