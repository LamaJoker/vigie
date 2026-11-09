# Feuille de route

14 étapes, une par semaine. Chaque étape est livrée par une ou plusieurs pull requests relues et validées, et se termine par un compte rendu dans [docs/semaines/](docs/semaines/).

## Phase 1 : les bases (semaines 1 à 5)

### Semaine 1 : poste de travail et Git

Compte rendu : [docs/semaines/semaine-01.md](docs/semaines/semaine-01.md)

- [x] Ubuntu installé sous WSL2, VS Code relié à WSL
- [x] Git configuré, dépôt publié sur GitHub
- [x] Travail organisé en pull requests
- [ ] Compte Linux sécurisé (mot de passe, `sudo` protégé)
- [ ] Clé SSH créée et ajoutée sur GitHub

### Semaine 2 : Linux et Bash (Vigie v0)

Compte rendu : [docs/semaines/semaine-02.md](docs/semaines/semaine-02.md)

- [x] Script Bash qui teste une liste d'URL avec `curl`
- [x] Résultats écrits dans un fichier de log
- [x] Lancement automatique toutes les 5 minutes avec `cron` (script d'installation)
- [x] Tests automatisés (bats) et analyse statique (ShellCheck)

### Semaine 3 : Python (Vigie v1)

Compte rendu : [docs/semaines/semaine-03.md](docs/semaines/semaine-03.md)

- [x] Sonde réécrite en Python, dans un environnement virtuel
- [x] Liste des sites dans un fichier de configuration (TOML)
- [x] Premiers tests automatisés avec pytest (51 tests, 99 % du code couvert)
- [x] Sites testés en parallèle, résultats au format JSON Lines
- [x] Makefile et contrôle du style avec ruff

### Semaine 4 : API et base de données

- [ ] Résultats stockés dans PostgreSQL
- [ ] API FastAPI pour consulter l'état des sites
- [ ] Page de statut simple

### Semaine 5 : alertes

- [ ] Notification Discord quand un site tombe et quand il revient
- [ ] Une seule alerte par incident (pas de spam)
- [ ] Configuration par variables d'environnement

## Phase 2 : construire et livrer (semaines 6 à 8)

### Semaine 6 : Docker

- [ ] Dockerfile multi-étapes, exécuté sans les droits root
- [ ] docker-compose qui lance la sonde, l'API et PostgreSQL

### Semaine 7 : intégration continue

- [ ] GitHub Actions : vérification du style et tests à chaque push
- [ ] Construction de l'image et publication sur GitHub Container Registry

### Semaine 8 : sécurité de la chaîne

- [ ] Scan des images avec Trivy
- [ ] Mises à jour des dépendances avec Dependabot
- [ ] Secrets sortis du code, branche `main` protégée

## Phase 3 : l'infrastructure (semaines 9 à 12)

### Semaine 9 : Terraform

- [ ] Infrastructure décrite en code, en local et sans frais
- [ ] Environnement détruit puis recréé à l'identique en une commande

### Semaine 10 : Ansible

- [ ] Machine configurée automatiquement : paquets, utilisateurs, pare-feu, Docker
- [ ] Déploiement de Vigie par Ansible

### Semaine 11 : Kubernetes

- [ ] Cluster local avec k3d
- [ ] Vigie déployée avec des manifestes, puis avec un chart Helm

### Semaine 12 : GitOps

- [ ] Argo CD installé dans le cluster
- [ ] Le cluster se met à jour tout seul quand le dépôt change

## Phase 4 : exploiter (semaines 13 et 14)

### Semaine 13 : supervision

- [ ] Prometheus collecte les métriques de Vigie
- [ ] Tableaux de bord Grafana, logs centralisés avec Loki
- [ ] Alertes sur les métriques

### Semaine 14 : bilan

- [ ] Sauvegarde et restauration de la base testées
- [ ] Procédures d'incident (runbooks)
- [ ] Schéma d'architecture et démonstration
