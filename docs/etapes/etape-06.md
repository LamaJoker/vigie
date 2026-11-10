# Étape 6 : Docker

**Date :** 9 novembre 2026
**Statut :** livrée en pull request

## Objectif

Emballer Vigie dans des conteneurs. Une seule commande doit lancer la base, l'API et la sonde, sur n'importe quelle machine qui a Docker, sans rien installer d'autre.

## Ce qui a été fait

### Docker sur le poste

- **Docker Engine 29** et **Docker Compose 2.40**, installés depuis les paquets d'Ubuntu dans WSL.
- **Le service Docker ne démarre pas avec Ubuntu** : c'est la première commande `docker` qui le réveille (activation par socket). Rien ne tourne quand on ne s'en sert pas.
- Le compte `valen` est dans le groupe `docker`, ce qui permet d'utiliser Docker sans `sudo`. **Attention :** ce groupe donne en pratique les droits root sur la machine, parce qu'un conteneur peut monter n'importe quel dossier. C'est acceptable sur un poste personnel, à éviter sur un serveur partagé.

### L'image (`Dockerfile`)

- **Construction en deux étapes (« multi-stage »)** : la première installe Vigie et ses dépendances, la seconde ne recopie que le résultat. L'image finale ne contient ni outils de construction, ni tests, ni documentation : **256 Mo**, dont l'essentiel est Python lui-même.
- **Cache des couches** : les fichiers qui changent le moins sont copiés en premier, pour que Docker réutilise les étapes déjà construites.
- **Utilisateur dédié sans droits root, avec un numéro fixe (UID 10001)**. Kubernetes (étape 11) a besoin d'un numéro pour vérifier qu'un conteneur ne tourne pas en root. hadolint, l'outil d'analyse des Dockerfile, l'a d'ailleurs signalé.
- **`.dockerignore`** : les secrets (`.env`), l'environnement virtuel, la base de développement et l'historique Git n'entrent jamais dans l'image.
- **Forme « exec » de `ENTRYPOINT`** : Vigie reçoit directement le signal d'arrêt.

### La pile (`compose.yaml`)

| Service | Rôle | Exposition |
|---|---|---|
| `base` | PostgreSQL 18, données dans un volume Docker | aucun port publié |
| `init-db` | crée les tables puis s'arrête | aucune |
| `api` | page de statut et API | `127.0.0.1:8000` seulement |
| `sonde` | `vigie surveiller` : un passage toutes les 5 minutes | aucune |

Choix et raisons :

- **Ordre de démarrage maîtrisé** : `init-db` attend que la base soit *saine*, l'API et la sonde attendent qu'`init-db` ait *réussi*. Un simple « démarré » ne suffit pas : PostgreSQL met quelques secondes à accepter les connexions.
- **Contrôles de santé** : `pg_isready` pour la base, `/sante` (créé à l'étape 4) pour l'API. `make docker-etat` affiche `healthy` ou `unhealthy`.
- **Redémarrage automatique** (`restart: unless-stopped`) si un conteneur plante.
- **Moindre privilège** pour les conteneurs Vigie : système de fichiers **en lecture seule** (seuls deux petits dossiers de travail en mémoire sont inscriptibles), **aucune capacité Linux** (`cap_drop: ALL`), et interdiction de gagner des droits (`no-new-privileges`).
- **Secrets hors du dépôt** : le mot de passe de la base est tiré au hasard par `make docker-demarrer` et rangé dans `.env`, avec les droits `600`. Le webhook Discord suit le même chemin.
- **La liste des sites est montée depuis la machine** : on modifie `config/vigie.toml` sans reconstruire l'image.

### La boucle de surveillance : `vigie surveiller`

Dans un conteneur, il n'y a pas de cron. La nouvelle commande `vigie surveiller` lance un passage, attend l'intervalle (`--intervalle` ou `VIGIE_INTERVALLE`), et recommence.

- **Arrêt propre** : `docker stop` envoie le signal SIGTERM. Vigie termine le passage en cours au lieu d'être coupé au milieu d'une écriture en base. Elle n'attend pas non plus la fin de l'intervalle.
- **Une erreur passagère n'arrête pas la boucle** (base injoignable, journal impossible à écrire). Une configuration invalide, elle, arrête tout de suite : inutile de boucler sur une erreur définitive.

## Incident : la sonde plantait dans son conteneur

**Ce qui s'est passé.** Au premier essai de bout en bout, la sonde plantait en boucle avec `PermissionError`. Le dossier de travail en mémoire (`tmpfs`) appartenait à root, et l'utilisateur 10001 ne pouvait pas y écrire son fichier verrou.

**Correction.** Le dossier est maintenant créé avec le bon propriétaire (`uid=10001`). Le code transforme aussi ce genre d'erreur en message clair, sans arrêter la surveillance. Trois tests reproduisent le cas sans Docker.

**Leçon.** Le durcissement (lecture seule, utilisateur non root) casse parfois des choses qui marchaient. Seul un essai dans les vraies conditions le révèle : c'est pour ça que l'essai de bout en bout existe.

## L'essai de bout en bout (`make tests-docker`)

Le script `tests/docker/essai-pile.sh` construit l'image et lance la pile dans un **projet jetable** (`vigie-essai`, port 18080). Il vérifie tout, puis supprime tout, données comprises. La vraie pile n'est jamais touchée.

```
=== L'API répond et sa base aussi            {"statut":"ok","base":"ok"}
=== La sonde a enregistré des mesures        5 site(s) mesuré(s)
=== La page de statut s'affiche              ok
=== Les conteneurs ne tournent pas en root   api : 10001, sonde : 10001
=== Système de fichiers en lecture seule     écriture refusée, comme prévu
=== La base n'est pas joignable de dehors    aucun port publié
=== La sonde s'arrête proprement (SIGTERM)   ok
TOUT EST BON
```

S'y ajoutent `make lint-docker` (hadolint et validation de `compose.yaml`) et **138 tests pytest** (10 nouveaux pour `vigie surveiller`, 99 % du code couvert).

## Limites connues

- **La pile complète n'a pas été laissée en marche sur le poste.** Avec le redémarrage automatique, elle relancerait ses conteneurs à chaque réveil de Docker. Pour la lancer : `make docker-demarrer`.
- **Les images de base ne sont pas figées** (`python:3.14-slim`, `postgres:18-alpine`) : deux constructions à des dates différentes peuvent donner des images différentes. On les fixera par leur empreinte (*digest*) à l'étape 8, avec l'analyse de sécurité.
- **Le mot de passe passe par une variable d'environnement**, visible avec `docker inspect`. Kubernetes (étape 11) apportera de vrais objets « Secret ».
- **Sous WSL, les conteneurs s'arrêtent avec Ubuntu.** Sur un vrai serveur, ils tourneront en continu.

## Comment vérifier

```bash
cd ~/vigie
make tests && make lint
make lint-docker
make tests-docker     # environ 1 minute : construit, lance, vérifie, nettoie
make docker-demarrer  # puis http://localhost:8000
make docker-arreter
```

## Vocabulaire de l'étape

| Terme | Sens |
|---|---|
| Image | Modèle figé d'un conteneur : le programme et tout ce dont il a besoin |
| Conteneur | Programme lancé à partir d'une image, isolé du reste de la machine |
| Dockerfile | Recette de construction d'une image |
| Multi-stage | Dockerfile en plusieurs étapes, dont seule la dernière forme l'image finale |
| Couche (layer) | Étape d'une image, mise en cache et réutilisée tant qu'elle ne change pas |
| Docker Compose | Outil qui décrit et lance plusieurs conteneurs ensemble |
| Volume | Espace de stockage qui survit à la suppression d'un conteneur |
| Healthcheck | Vérification régulière qu'un conteneur fonctionne vraiment |
| SIGTERM | Signal « arrête-toi proprement » envoyé par `docker stop` |
| Moindre privilège | Ne donner à un programme que les droits dont il a strictement besoin |

## Temps de supervision

| Jour | Activité | Durée |
|---|---|---|
| Lun. 9/11 | Relecture de la pull request de l'étape 6 | |

**Total :** h
