# Semaine 2 : Linux et Bash (Vigie v0)

**Date :** 9 novembre 2026 (étape avancée à la demande du superviseur)
**Statut :** livrée en pull request ; tâche cron pas encore installée sur le poste

## Objectif

Une première version de Vigie, la plus simple possible : un script Bash qui teste une liste de sites, écrit les résultats dans un fichier, et peut tourner tout seul toutes les 5 minutes.

## Ce qui a été fait

### La sonde : `sonde/vigie.sh`

Pour chaque adresse de `sonde/sites.txt`, la sonde envoie une requête avec `curl`, mesure le code HTTP et le temps de réponse, puis ajoute une ligne au log :

```
2026-11-09T15:00:06+01:00 UP 200 205 https://www.wikipedia.org
```

Choix et raisons :

- **`curl --max-time`** : un site qui ne répond pas ne bloque jamais la sonde plus de 10 secondes (réglable avec `VIGIE_DELAI`).
- **Code `000`** : quand il n'y a aucune réponse (adresse inconnue, connexion refusée, délai dépassé), curl renvoie ce code. La sonde le note `DOWN`.
- **`UP` = codes 2xx et 3xx** ; tout le reste est `DOWN`. Les redirections sont suivies (`--location`).
- **Codes de sortie** : `0` si tout va bien, `1` si au moins un site est en panne, `2` en cas d'erreur d'utilisation. C'est la convention Unix : un autre programme (cron, une alerte, la CI) peut réagir sans lire le texte.
- **Log dans `~/.local/state/vigie/`** : c'est l'emplacement standard sous Linux pour les données qu'un programme produit (norme XDG). Les résultats ne sont jamais mélangés au code du dépôt.
- **Verrou avec `flock`** : si une sonde est encore en cours quand cron en lance une autre, la deuxième s'arrête au lieu de doubler les mesures.
- **`set -euo pipefail`** : le script s'arrête à la première erreur inattendue, au lieu de continuer avec des données fausses.
- **Un « user agent » identifiable** (`vigie/0.1`) : un administrateur qui voit passer nos requêtes sait d'où elles viennent.

### Le lancement automatique : `sonde/installer-cron.sh`

`cron` est le planificateur de tâches historique de Linux. La ligne installée :

```
*/5 * * * * /home/valen/vigie/sonde/vigie.sh >/dev/null 2>>~/.local/state/vigie/erreurs.log
```

Les cinq premiers champs donnent minute, heure, jour du mois, mois et jour de la semaine : `*/5 * * * *` veut dire « toutes les 5 minutes ». Les messages d'erreur sont gardés dans `erreurs.log`.

Le script est **idempotent** : on peut le relancer autant de fois qu'on veut, il remplace sa ligne au lieu d'en ajouter une deuxième, et ne touche pas aux autres tâches. `--retirer` enlève la tâche.

### La qualité : tests et analyse statique

- **ShellCheck** analyse les scripts sans les exécuter et repère les pièges classiques de Bash (variables non protégées par des guillemets, etc.). Résultat : aucun problème.
- **bats** (Bash Automated Testing System) exécute **17 tests** :
  - 12 pour la sonde, contre un petit serveur HTTP local (`tests/serveur_test.py`) qui répond le code demandé ou fait exprès d'être lent. Les tests ne dépendent donc ni d'Internet ni de sites extérieurs ;
  - 5 pour l'installation cron, avec une fausse commande `crontab` qui écrit dans un fichier : la vraie crontab n'est jamais touchée.

## Incident : un défaut trouvé par les tests

Le premier essai de l'installeur cron lisait la crontab et la réécrivait **dans la même commande** (`crontab -l | … | crontab -`). Les tests ont montré que, selon l'ordre d'exécution, les tâches existantes pouvaient être effacées. Avec la vraie commande `crontab`, ça fonctionne par chance, parce qu'elle lit tout avant d'écrire. Mais un script ne doit pas dépendre de la chance.

**Correction :** le nouveau contenu est entièrement calculé d'abord, puis installé en une fois. **Leçon :** tester sur une copie (ici, une fausse commande) permet de trouver un défaut sans risquer la vraie configuration.

## Premier essai réel

```
2026-11-09T15:00:06+01:00 UP 200 205 https://www.wikipedia.org
2026-11-09T15:00:06+01:00 UP 200 196 https://github.com
2026-11-09T15:00:06+01:00 UP 200 150 https://www.debian.org
2026-11-09T15:00:06+01:00 UP 200 205 https://www.data.gouv.fr
2026-11-09T15:00:07+01:00 UP 200 73 https://example.com
```

## Limites connues (traitées dans les semaines suivantes)

- **Sous WSL, Ubuntu s'arrête quand plus aucune fenêtre ne l'utilise** : cron ne tourne alors plus. Sur un vrai serveur (semaines 9 et 10), la sonde tournera en continu.
- **Les sites sont testés l'un après l'autre** : avec beaucoup de sites, un passage peut devenir long. La version Python (semaine 3) les testera en parallèle.
- **Le log grossit sans fin** : il faudra une rotation ou une base de données (semaine 4).
- **Aucune alerte** : une panne est notée mais personne n'est prévenu (semaine 5).

## Comment vérifier

```bash
cd ~/vigie
./sonde/vigie.sh; echo "code de sortie : $?"
shellcheck sonde/*.sh
bats tests/bash/   # les tests Bash ont été rangés dans tests/bash/ en semaine 3
```

Pour activer le lancement automatique : `./sonde/installer-cron.sh`, puis `crontab -l` pour voir la tâche.

## Vocabulaire de la semaine

| Terme | Sens |
|---|---|
| Sonde | Programme qui vérifie régulièrement qu'un service répond |
| Code HTTP | Nombre renvoyé par un site : 200 = OK, 404 = introuvable, 503 = indisponible |
| Code de sortie | Nombre renvoyé par un programme à la fin : 0 = succès, autre = problème |
| cron / crontab | Planificateur de tâches de Linux / liste des tâches planifiées d'un utilisateur |
| Idempotent | Qu'on peut relancer sans changer le résultat au-delà du premier lancement |
| Verrou (`flock`) | Mécanisme qui empêche deux exécutions simultanées |
| Analyse statique | Vérification du code sans l'exécuter (ShellCheck) |
| Test automatisé | Script qui vérifie qu'un programme se comporte comme prévu (bats) |

## Temps de supervision

| Jour | Activité | Durée |
|---|---|---|
| Lun. 9/11 | Relecture de la pull request de la semaine 2 | |

**Total :** h
