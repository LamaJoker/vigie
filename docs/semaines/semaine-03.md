# Semaine 3 : Python (Vigie v1)

**Date :** 9 novembre 2026 (étape avancée à la demande du superviseur)
**Statut :** livrée en pull request

## Objectif

Réécrire la sonde en Python, avec une vraie configuration et des tests, pour préparer la suite : API, base de données, conteneurs.

## Ce qui a été fait

### Un paquet Python installable

- **`pyproject.toml`** décrit le projet : nom, version, dépendances, et la commande `vigie` qu'il installe. C'est le format standard actuel d'un projet Python.
- **Une seule dépendance d'exécution : `httpx`**, un client HTTP qui sait faire plusieurs requêtes en même temps. Les outils de développement (pytest, pytest-cov, ruff) sont séparés dans `[dev]` : ils ne seront pas installés en production.
- **Environnement virtuel `.venv`** : les bibliothèques du projet sont isolées de celles du système. Deux projets peuvent ainsi utiliser des versions différentes sans conflit.
- **`Makefile`** : `make installer`, `make tests`, `make lint`, `make sonder`. Les mêmes commandes serviront dans l'intégration continue (semaine 7).

### Le code (`src/vigie/`)

| Fichier | Rôle |
|---|---|
| `config.py` | lit `config/vigie.toml` et le valide |
| `sonde.py` | teste les sites, en parallèle |
| `journal.py` | ajoute les résultats au fichier JSON Lines |
| `cli.py` | la commande `vigie sonder` |

Choix et raisons :

- **Configuration en TOML** (`config/vigie.toml`) : lisible par un humain, et Python sait le lire sans dépendance. Chaque erreur (adresse invalide, adresse en double, délai négatif…) est refusée avec un message clair **avant** de lancer la moindre requête.
- **Tests en parallèle (`asyncio`)** : pendant qu'un site met du temps à répondre, la sonde en interroge d'autres. Une limite (`paralleles`) évite d'ouvrir trop de connexions d'un coup. Avec 5 sites, un passage dure le temps du site le plus lent (environ 0,25 s) au lieu de la somme de tous (environ 0,8 s en Bash).
- **Délai total par site** : comme `curl --max-time`, il compte les redirections. Un site ne bloque jamais la sonde plus de `delai` secondes.
- **Résultats en JSON Lines** (`~/.local/state/vigie/sondes.jsonl`) : un objet JSON par ligne. Le format reste lisible, se filtre avec `jq` et sera compris tel quel par Loki (semaine 13).
- **Mêmes conventions que la version Bash** : codes de sortie 0, 1 et 2, verrou contre les exécutions simultanées, variables d'environnement `VIGIE_CONFIG` et `VIGIE_LOG`. Ces variables permettront de configurer le conteneur Docker sans modifier le code (semaine 6).

### Les tests (`tests/python/`)

**51 tests pytest**, qui couvrent 99 % du code :

- **configuration** (30 tests) : fichier valide, valeurs par défaut, et chaque cas d'erreur ;
- **sonde** (10 tests) avec un **faux réseau** (`httpx.MockTransport`) : on décide de la réponse de chaque « site » sans Internet. On vérifie les codes 200 et 503, les redirections, la connexion refusée, le délai dépassé, le parallélisme réel, la limite de requêtes simultanées et l'ordre des résultats ;
- **commande complète** (11 tests) contre un **vrai petit serveur HTTP local**, lancé par les tests eux-mêmes.

Les 17 tests Bash de la semaine 2 ont été rangés dans `tests/bash/`.

### La qualité

**ruff** vérifie le style (norme PEP 8), l'ordre des imports et les pièges courants, et met le code en forme automatiquement. `make lint` lance ruff et ShellCheck.

## Incident : Wikipédia refuse la sonde Python

**Ce qui s'est passé.** Au premier essai réel, Wikipédia a répondu `403` (accès refusé) à la sonde Python, alors qu'elle répondait `200` à la version Bash. Le message de refus renvoyait à la politique de Wikimedia pour les robots.

**Diagnostic.** Un petit script a comparé plusieurs identifiants (*User-Agent*) envoyés par la sonde. Wikipédia refuse les robots qui ne donnent pas de moyen de contacter leur auteur. Elle accepte dès que l'identifiant contient l'adresse du projet : `vigie/0.2 (+https://github.com/LamaJoker/vigie; …)`.

**Correction.** Les deux sondes, Python et Bash, envoient désormais cet identifiant, et un test vérifie qu'il contient bien le moyen de contact.

**Leçon.** Les tests sur un faux réseau prouvent que la logique est juste, mais seul un essai réel révèle les règles des vrais sites. Les deux sont nécessaires.

## Autre point appris en route

Un script Bash modifié depuis Windows avait perdu son droit d'exécution, et les tests Bash ont échoué avec « Permission denied ». C'est corrigé (`chmod +x`). Leçon : sous Linux, le droit d'exécution fait partie du fichier, et Git l'enregistre avec lui.

## Premier essai réel

```
UP   200    194 ms  Wikipédia (https://www.wikipedia.org)
UP   200    250 ms  GitHub (https://github.com)
UP   200    118 ms  Debian (https://www.debian.org)
UP   200    180 ms  data.gouv.fr (https://www.data.gouv.fr)
UP   200     95 ms  Example (https://example.com)
```

## Limites connues

- **Le fichier de résultats grossit sans fin** : la base de données PostgreSQL de la semaine 4 le remplacera.
- **Pas encore d'interface** : les résultats se lisent dans le terminal ou dans le fichier. L'API et la page de statut arrivent en semaine 4.
- **La tâche cron lance toujours la version Bash** : la version Python sera planifiée quand elle tournera dans un conteneur (semaine 6).

## Comment vérifier

```bash
cd ~/vigie
make installer
make tests     # 51 tests Python et 17 tests Bash
make lint      # ruff et ShellCheck
make sonder    # essai réel
```

## Vocabulaire de la semaine

| Terme | Sens |
|---|---|
| Environnement virtuel (venv) | Dossier qui isole les bibliothèques d'un projet Python |
| Dépendance | Bibliothèque dont le projet a besoin (ici `httpx`) |
| `pyproject.toml` | Fiche d'identité d'un projet Python : nom, version, dépendances, commandes |
| TOML | Format de fichier de configuration lisible (`clé = valeur`) |
| Asynchrone (`asyncio`) | Faire avancer plusieurs tâches en attendant les réponses du réseau |
| JSON Lines | Un objet JSON par ligne, pratique pour les journaux |
| Mock (simulacre) | Faux composant qui remplace le vrai dans les tests (ici, le réseau) |
| Couverture de code | Part du code exécutée par les tests (99 % ici) |
| Linter (ruff) | Outil qui vérifie le style et repère les erreurs probables |
| User-Agent | Identifiant qu'un programme envoie à chaque site qu'il interroge |

## Temps de supervision

| Jour | Activité | Durée |
|---|---|---|
| Lun. 9/11 | Relecture de la pull request de la semaine 3 | |

**Total :** h
