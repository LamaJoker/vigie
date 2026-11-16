# Feuille de route

14 étapes. Chaque étape est découpée en **lots**. Un lot = une branche = une pull request relue et validée. Chaque étape se termine par un compte rendu dans [docs/etapes/](docs/etapes/), et à partir de l'étape 8 par une version publiée.

Les lots à venir ont chacun un ticket, rangé dans le jalon de son étape ([vue d'ensemble des jalons](https://github.com/LamaJoker/vigie/milestones)). Le détail de ce qu'il faut livrer et du critère « terminé quand » est dans le ticket.

## Phase 1 : les bases (étapes 1 à 5)

### Étape 1 : poste de travail et Git

Compte rendu : [docs/etapes/etape-01.md](docs/etapes/etape-01.md)

- [x] Ubuntu installé sous WSL2, VS Code relié à WSL
- [x] Git configuré, dépôt publié sur GitHub
- [x] Travail organisé en pull requests
- [ ] Compte Linux sécurisé (mot de passe, `sudo` protégé) : action du superviseur
- [ ] Clé SSH créée et ajoutée sur GitHub : action du superviseur

### Étape 2 : Linux et Bash (Vigie v0)

Compte rendu : [docs/etapes/etape-02.md](docs/etapes/etape-02.md)

- [x] Script Bash qui teste une liste d'URL avec `curl`
- [x] Résultats écrits dans un fichier de log
- [x] Lancement automatique toutes les 5 minutes avec `cron` (script d'installation)
- [x] Tests automatisés (bats) et analyse statique (ShellCheck)

### Étape 3 : Python (Vigie v1)

Compte rendu : [docs/etapes/etape-03.md](docs/etapes/etape-03.md)

- [x] Sonde réécrite en Python, dans un environnement virtuel
- [x] Liste des sites dans un fichier de configuration (TOML)
- [x] Premiers tests automatisés avec pytest (51 tests, 99 % du code couvert)
- [x] Sites testés en parallèle, résultats au format JSON Lines
- [x] Makefile et contrôle du style avec ruff

### Étape 4 : API et base de données

Compte rendu : [docs/etapes/etape-04.md](docs/etapes/etape-04.md)

- [x] Résultats stockés dans PostgreSQL
- [x] API FastAPI pour consulter l'état des sites
- [x] Page de statut simple
- [x] Point de contrôle `/sante`, tests sur une vraie base jetable

### Étape 5 : alertes

Compte rendu : [docs/etapes/etape-05.md](docs/etapes/etape-05.md)

- [x] Notification Discord quand un site tombe et quand il revient
- [x] Une seule alerte par incident (pas de spam), garantie par la base
- [x] Configuration par variables d'environnement (`.env`, jamais commité)
- [x] Alerte renvoyée au passage suivant si Discord ne l'a pas reçue
- [x] Incidents affichés sur la page de statut et dans l'API

## Phase 2 : construire, livrer, durcir (étapes 6 à 8)

### Étape 6 : Docker

Compte rendu : [docs/etapes/etape-06.md](docs/etapes/etape-06.md)

- [x] Dockerfile multi-étapes, exécuté sans les droits root
- [x] Docker Compose qui lance la sonde, l'API et PostgreSQL
- [x] Contrôles de santé, arrêt propre (SIGTERM), conteneurs en lecture seule
- [x] Essai de bout en bout automatisé de la pile

### Étape 7 : intégration continue

Compte rendu : [docs/etapes/etape-07.md](docs/etapes/etape-07.md)

- [x] GitHub Actions : vérification du style et tests à chaque push
- [x] Construction de l'image et publication sur GitHub Container Registry (premier passage réussi le 10/11/2026)
- [x] Tests sur deux versions de Python, couverture minimale exigée
- [x] Mêmes vérifications en local avec `make ci`

### Lot 0 : revue et nouvelle feuille de route ([#8](https://github.com/LamaJoker/vigie/issues/8))

- [x] Revue complète du projet : dix défauts trouvés, traités à l'étape 8
- [x] « Semaines » renommées en « étapes » ; feuille de route découpée en lots ; jalons et tickets
- [x] Décisions d'architecture, schéma d'architecture, journal des versions, licence MIT

### Étape 8 : durcissement (version 0.8.0)

Avant de déployer Vigie sur des serveurs et dans un cluster, la rendre fiable, puis sécuriser la chaîne qui la construit.

- [x] Lot 8.1 : une sonde qui ne tombe pas, même avec une adresse mal écrite ([#9](https://github.com/LamaJoker/vigie/issues/9)) ; compte rendu : [docs/etapes/etape-08.md](docs/etapes/etape-08.md)
- [ ] Lot 8.2 : une page qui ne ment pas : heure locale, données périmées signalées ([#10](https://github.com/LamaJoker/vigie/issues/10))
- [ ] Lot 8.3 : une base qui dure : migrations, rétention, pool de connexions ([#11](https://github.com/LamaJoker/vigie/issues/11))
- [ ] Lot 8.4 : une construction reproductible : dépendances verrouillées, images et actions épinglées, Dependabot ([#12](https://github.com/LamaJoker/vigie/issues/12))
- [ ] Lot 8.5 : l'analyse de sécurité dans la CI : failles, secrets, code ([#13](https://github.com/LamaJoker/vigie/issues/13))
- [ ] Lot 8.6 : des versions publiées et signées, une branche `main` protégée ([#14](https://github.com/LamaJoker/vigie/issues/14))

## Phase 3 : l'infrastructure (étapes 9 à 12)

### Étape 9 : Terraform (version 0.9.0)

Des « serveurs » locaux et gratuits, créés et détruits par du code.

- [ ] Lot 9.1 : essai de faisabilité d'Incus sur le poste ([#15](https://github.com/LamaJoker/vigie/issues/15))
- [ ] Lot 9.2 : l'infrastructure en code : deux environnements, détruits et recréés à l'identique ([#16](https://github.com/LamaJoker/vigie/issues/16))

### Étape 10 : Ansible (version 0.10.0)

- [ ] Lot 10.1 : le socle des serveurs : paquets, comptes, SSH, pare-feu, PostgreSQL, Docker ([#17](https://github.com/LamaJoker/vigie/issues/17))
- [ ] Lot 10.2 : le déploiement de Vigie en HTTPS, avec retour arrière automatique ([#18](https://github.com/LamaJoker/vigie/issues/18))

### Étape 11 : Kubernetes (version 0.11.0)

- [ ] Lot 11.1 : préparer l'application et le cluster k3d ([#19](https://github.com/LamaJoker/vigie/issues/19))
- [ ] Lot 11.2 : le chart Helm, durci ([#20](https://github.com/LamaJoker/vigie/issues/20))

### Étape 12 : GitOps (version 0.12.0)

- [ ] Lot 12.1 : Argo CD, recette et production, promotion par pull request ([#21](https://github.com/LamaJoker/vigie/issues/21))

## Phase 4 : exploiter (étapes 13 et 14)

### Étape 13 : observabilité (version 0.13.0)

- [ ] Lot 13.1 : instrumenter l'application : métriques Prometheus, journaux JSON ([#22](https://github.com/LamaJoker/vigie/issues/22))
- [ ] Lot 13.2 : la pile de supervision : tableaux de bord, alertes sur la plateforme elle-même ([#23](https://github.com/LamaJoker/vigie/issues/23))

### Étape 14 : exploitation et bilan (version 1.0.0)

- [ ] Lot 14.1 : sauvegarder, restaurer, dépanner : restauration testée, fiches d'exploitation, exercices de panne ([#24](https://github.com/LamaJoker/vigie/issues/24))
- [ ] Lot 14.2 : la documentation finale ([#25](https://github.com/LamaJoker/vigie/issues/25))
