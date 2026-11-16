# 0007. Tout ce qui est téléchargé pour construire Vigie est désigné par une empreinte

- **Statut :** acceptée
- **Date :** 2026-11-16

## Contexte

Jusqu'au lot 8.3, la construction de Vigie téléchargeait des choses désignées par des **étiquettes mobiles** :

- les actions GitHub par une version majeure (`actions/checkout@v5`) ;
- les images Docker par une étiquette (`python:3.14-slim`, `postgres:18-alpine`, `hadolint/hadolint:latest-debian`) ;
- les dépendances Python par des bornes (`fastapi>=0.115`), résolues à la date de la construction.

Une étiquette n'est qu'un nom qui pointe vers un contenu, et ce nom peut être déplacé. En mars 2025, des attaquants ont pris la main sur l'action `tj-actions/changed-files`, utilisée par plus de 20 000 dépôts. Ils ont **redirigé ses étiquettes de version** vers un code qui recopiait les secrets de la CI dans les journaux publics (CVE-2025-30066). Les dépôts qui désignaient l'action par une étiquette ont exécuté ce code sans rien changer de leur côté. Ceux qui la désignaient par le SHA d'un commit n'ont rien exécuté.

Sans aller jusqu'à l'attaque, une étiquette mobile rend aussi la construction **non reproductible** : la même version du code peut donner deux images différentes à une semaine d'écart.

## Décision

Tout ce que la construction télécharge est désigné par une **empreinte**, c'est-à-dire par son contenu exact :

| Quoi | Comment | Où |
|---|---|---|
| Dépendances Python | `uv.lock` : version exacte et empreinte SHA-256 de chaque paquet, calculées pour toutes les versions de Python acceptées | installées par `uv sync --locked`, qui refuse tout paquet dont l'empreinte diffère |
| Images Docker | `nom:étiquette@sha256:…`, l'étiquette restant pour la lecture | Dockerfile, `compose.yaml`, Makefile |
| Actions GitHub | SHA complet du commit, version en commentaire | `.github/workflows/` |
| uv lui-même | version fixée (`required-version`), archive vérifiée par son empreinte | `pyproject.toml`, `scripts/installer-uv.sh`, Dockerfile |
| Outil de construction du paquet | `uv_build`, intégré à uv : rien d'autre à télécharger | `pyproject.toml` |

- **Un contrôle automatique** (`scripts/verifier_epinglage.py`, dans `make lint` et la CI) refuse toute référence sans empreinte.
- **Dependabot** propose chaque lundi les nouvelles versions par pull request. Les mises à jour mineures sont groupées, et une version doit avoir 7 jours avant d'être proposée : une version piégée est souvent repérée et retirée dans les premiers jours. Chaque proposition passe par la CI comme le reste.
- **uv** gère le verrou. Son verrou est universel : un seul fichier vaut pour Python 3.12 à 3.14 et pour toutes les machines.

## Conséquences

- Deux constructions du même commit donnent les mêmes paquets, aux mêmes versions.
- Un paquet altéré, sur le registre ou en route, est refusé à l'installation : la construction échoue.
- Les mises à jour ne se font plus toutes seules : il faut fusionner les pull requests de Dependabot. C'est voulu. Chaque mise à jour est visible, testée, et réversible par un simple retour en arrière.
- Les fichiers sont moins lisibles : un SHA ne dit rien à un humain, d'où la version en commentaire.
- Ce qui reste hors du verrou est connu et noté dans le compte rendu du lot 8.4 : les paquets système installés par `apt` dans la CI, et les programmes préinstallés sur les machines de GitHub.

## Solutions écartées

- **pip-tools** (`pip-compile --generate-hashes`) : solide et répandu, mais un fichier de verrou par version de Python, alors que la CI en teste deux.
- **Poetry** : son verrou est aussi universel, mais il impose son propre format de projet et une installation plus lourde. uv suit les formats standard de `pyproject.toml`.
- **Épingler seulement les versions, sans empreintes** : protège contre les surprises de versions, pas contre un fichier remplacé sur le registre.
- **Renovate au lieu de Dependabot** : plus réglable, mais demande une application tierce. Dependabot est intégré à GitHub et gratuit.
