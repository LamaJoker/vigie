# Feuille de route

14 semaines, environ 20 heures par semaine. Chaque semaine se termine par une entrée dans le [journal de bord](docs/journal/) et au moins un commit poussé sur GitHub.

## Phase 1 : les bases (semaines 1 à 5)

### Semaine 1 : poste de travail et Git

Guide : [docs/guides/semaine-01.md](docs/guides/semaine-01.md)

- [x] Ubuntu installé sous WSL2, VS Code relié à WSL
- [x] Git configuré, premier commit
- [ ] Dépôt publié sur GitHub
- [ ] Compte Linux sécurisé (mot de passe, `sudo` protégé)
- [ ] Bases du terminal Linux
- [ ] Clé SSH créée et ajoutée sur GitHub

### Semaine 2 : Linux et Bash (Vigie v0)

- [ ] Script Bash qui teste une liste d'URL avec `curl`
- [ ] Résultats écrits dans un fichier de log
- [ ] Lancement automatique toutes les 5 minutes avec `cron`

### Semaine 3 : Python (Vigie v1)

- [ ] Sonde réécrite en Python, dans un environnement virtuel
- [ ] Liste des sites dans un fichier de configuration
- [ ] Premiers tests automatisés avec pytest

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
