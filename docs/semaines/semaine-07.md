# Semaine 7 : intégration continue

**Date :** 9 novembre 2026 (étape avancée à la demande du superviseur)
**Statut :** livrée en pull request

## Objectif

Ne plus dépendre de la mémoire de quelqu'un pour lancer les vérifications. À chaque modification proposée, GitHub vérifie tout automatiquement, et une version validée de Vigie est publiée sous forme d'image Docker.

## Ce qui a été fait

### Le workflow `.github/workflows/ci.yml`

GitHub Actions exécute ce fichier sur des machines Linux fournies par GitHub, à chaque pull request et à chaque modification de `main` :

| Étape (job) | Contenu | Durée indicative |
|---|---|---|
| Style et analyse | ruff, ShellCheck, hadolint, validation de `compose.yaml` | ~1 min |
| Tests Python 3.12 et 3.14 | pytest avec une base PostgreSQL jetable, couverture d'au moins 95 % | ~1 min chacun |
| Tests Bash | bats | < 1 min |
| Image et essai | construction de l'image et essai de bout en bout de la pile | ~2 min |
| Publication | sur `main` seulement : publication de l'image sur GitHub Container Registry | < 1 min |

Les quatre premières étapes tournent **en parallèle**. L'image n'est construite que si tout le reste est vert, et elle n'est publiée que si son essai a réussi.

Choix et raisons :

- **Deux versions de Python** (une « matrice ») : la plus ancienne acceptée par `pyproject.toml` (3.12) et la plus récente (3.14). Un code qui marche sur le poste du développeur mais pas en production, c'est l'erreur classique que la matrice évite.
- **Couverture minimale exigée (95 %)** : une modification qui ajoute du code sans tests fait échouer la vérification.
- **L'image publiée est exactement celle qui a été testée** : elle passe d'une étape à l'autre comme un fichier (un *artefact*), sans être reconstruite.
- **Étiquettes de l'image** : le numéro court du commit (par exemple `ghcr.io/lamajoker/vigie:9d5b275`), pour savoir exactement quel code tourne, et `latest` pour la dernière version.
- **Une pull request ne publie jamais rien** : seule une modification fusionnée dans `main` le peut.

### La sécurité de la chaîne

- **Droits minimaux** : par défaut, le workflow peut seulement lire le dépôt. Le droit d'écrire dans le registre d'images (`packages: write`) n'est donné qu'à l'étape de publication.
- **Aucun secret personnel** : la publication utilise `GITHUB_TOKEN`, un jeton temporaire que GitHub crée pour chaque passage et détruit ensuite.
- **Pas d'injection dans les scripts** : les valeurs venant de GitHub (nom de l'auteur, jeton) passent par des variables d'environnement, jamais collées directement dans les commandes.
- **Pas de doublons inutiles** : une nouvelle modification sur une pull request annule la vérification devenue obsolète. Sur `main`, en revanche, on va toujours au bout.

### Les mêmes vérifications sur le poste : `make ci`

`make ci` lance en local tout ce que fait GitHub (style, analyse, tests, essai Docker), plus **actionlint**, qui vérifie le workflow lui-même. On sait ainsi avant de pousser si la vérification passera.

## Vérification en local

```
actionlint                       aucun problème
ruff, ShellCheck                 aucun problème
hadolint, compose.yaml           aucun problème
pytest                           138 tests réussis
bats                             17 tests réussis
essai de bout en bout Docker     TOUT EST BON
```

## Un droit à ajouter côté GitHub

GitHub refuse qu'un programme ajoute ou modifie un workflow sans le droit spécial `workflow` : un workflow peut exécuter du code avec les droits du dépôt. La connexion GitHub du poste n'avait pas ce droit. Le superviseur doit l'accorder lui-même (`gh auth refresh -s workflow`) : c'est une autorisation de son compte, que l'assistant ne peut pas se donner.

## Limites connues

- **Les actions GitHub utilisées sont désignées par leur version majeure** (`actions/checkout@v5`). Une version modifiée en douce serait utilisée sans prévenir. On les fixera par leur empreinte, avec Dependabot pour les mettre à jour (semaine 8).
- **La branche `main` n'est pas encore protégée** : on peut toujours fusionner une pull request dont la vérification a échoué (semaine 8).
- **L'image publiée n'est pas encore analysée** pour ses failles connues (Trivy, semaine 8).

## Comment vérifier

- Onglet **Actions** du dépôt : chaque passage, ses étapes et leurs journaux.
- Dans la pull request : les coches vertes ou les croix rouges en bas de page.
- En local : `make ci`.

## Vocabulaire de la semaine

| Terme | Sens |
|---|---|
| Intégration continue (CI) | Vérification automatique de chaque modification, dès qu'elle est proposée |
| Livraison continue (CD) | Publication automatique d'une version prête à déployer |
| Workflow | Fichier qui décrit un enchaînement d'étapes automatiques dans GitHub Actions |
| Job | Une étape du workflow, exécutée sur sa propre machine |
| Runner | Machine qui exécute les jobs (ici fournie par GitHub) |
| Matrice | Même job lancé avec plusieurs réglages (ici, deux versions de Python) |
| Artefact | Fichier produit par un job et transmis à un autre |
| Registre d'images | Entrepôt d'images Docker (ici GitHub Container Registry, `ghcr.io`) |
| `GITHUB_TOKEN` | Jeton temporaire fourni par GitHub à chaque passage, avec des droits limités |

## Temps de supervision

| Jour | Activité | Durée |
|---|---|---|
| Lun. 9/11 | Relecture de la pull request de la semaine 7 | |

**Total :** h
