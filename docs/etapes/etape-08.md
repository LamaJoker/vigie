# Étape 8 : durcissement

**Date :** à partir du 10 novembre 2026 (lot 8.1 : 10-11 novembre ; lots 8.2 à 8.4 : 16 novembre)
**Statut :** en cours (lots 8.1 à 8.4 livrés)
**Lots :** [#9](https://github.com/LamaJoker/vigie/issues/9) 8.1 · [#10](https://github.com/LamaJoker/vigie/issues/10) 8.2 · [#11](https://github.com/LamaJoker/vigie/issues/11) 8.3 · [#12](https://github.com/LamaJoker/vigie/issues/12) 8.4 · [#13](https://github.com/LamaJoker/vigie/issues/13) 8.5 · [#14](https://github.com/LamaJoker/vigie/issues/14) 8.6

## Objectif

Avant de déployer Vigie sur des serveurs et dans un cluster, la rendre fiable, puis sécuriser la chaîne qui la construit. Les défauts traités ici viennent de la revue du 10/11/2026, où chacun a été reproduit.

## Lot 8.1 : une sonde qui ne tombe pas

### Le problème

Une seule adresse mal écrite dans la configuration suffisait à arrêter toute la surveillance. Avec `https://example.com:99999`, la configuration était acceptée, puis le passage entier plantait : plus aucun site n'était mesuré. Dans le conteneur, la sonde aurait redémarré en boucle. D'autres cas produisaient une trace Python illisible au lieu d'un message clair.

### Ce qui a été fait

**1. Les adresses sont vérifiées au chargement de la configuration.** Une adresse est refusée, avec un message qui dit pourquoi et le code de sortie 2, si :

| Cas | Exemple | Avant |
|---|---|---|
| port hors limites ou non numérique | `https://example.com:99999` | plantage de tout le passage |
| adresse IPv6 mal refermée | `http://[::1` | trace Python |
| espace ou caractère invisible | `https://exa mple.com`, octet nul | `DOWN` à chaque passage, ou plantage |
| pas de nom d'hôte | `https://:443/` | acceptée |
| plus de 2 000 caractères | une adresse de 70 000 caractères | acceptée |

Le message ne recopie jamais une adresse géante en entier. Un fichier qui n'est pas en UTF-8, ou un dossier à la place du fichier, donne aussi un message clair.

*Pourquoi refuser au chargement plutôt que noter le site `DOWN` ?* Une adresse mal écrite est une erreur de configuration, pas une panne du site. La noter `DOWN` déclencherait une fausse alerte et laisserait croire que le site est tombé.

**2. Une erreur imprévue n'arrête plus les autres sites.** La sonde attrapait déjà les erreurs réseau connues. Désormais, toute autre erreur (un bug, un cas limite d'une bibliothèque) donne un résultat `DOWN` avec la cause « erreur interne (type de l'erreur) ». La trace complète part dans le journal pour qu'on puisse corriger, et les autres sites sont mesurés normalement.

**3. La sonde ne télécharge plus le corps des pages.** Elle lit le code et les en-têtes, puis ferme la connexion (lecture « en flux »). Seul le code compte pour savoir si un site répond. Le reste coûtait du temps, de la mémoire et de la bande passante, et une adresse vers un gros fichier aurait pu bloquer la sonde jusqu'au délai maximal. **Conséquence à connaître :** le temps mesuré s'arrête maintenant à la réception des en-têtes. Il est plus court qu'avant et pas directement comparable.

**4. La boucle de surveillance résiste aux erreurs, avec un garde-fou.** `vigie surveiller` continue après une erreur imprévue d'un passage, et garde sa trace. Mais après **5 erreurs imprévues de suite**, elle s'arrête avec le code 1. Un problème permanent ne doit pas tourner en silence : en s'arrêtant, la sonde laisse Docker ou Kubernetes la relancer, et le compteur de redémarrages rend le problème visible.

**5. Un site retiré de la configuration ne laisse plus d'incident « en cours ».** Son incident est fermé avec le motif « site retiré de la surveillance », sans alerte, et une alerte encore en attente pour lui ne part plus. La table des incidents gagne une colonne `motif_fin`. Rejouer le schéma l'ajoute aussi aux bases existantes, comme le vérifie un test.

### Les tests : d'abord rouges, puis verts

**22 nouveaux tests** (164 au total, 99 % du code couvert). Chacun a d'abord été lancé contre le code d'avant le lot, **où les 22 échouent**. C'est la preuve qu'ils détectent vraiment les défauts. Après la correction, ils passent tous.

Un test a dû être renforcé en route. Le test « retirer un site en panne » vérifiait seulement qu'aucune alerte ne partait. Il passait aussi sur l'ancien code, qui n'en envoyait pas non plus, tout en laissant l'incident ouvert pour toujours. Il vérifie maintenant que l'incident est fermé. Leçon : **un test qu'on n'a jamais vu échouer ne prouve rien.**

Le test de la page géante utilise un faux site qui annonce 50 Mo et les envoie au compte-gouttes. Il lui faudrait plus de 40 secondes pour tout envoyer : la sonde répond `UP` en moins d'une seconde.

### Essais réels

**Port impossible au milieu de vrais sites**, ancien code puis nouveau :

```
=== ANCIEN code
    | OverflowError: connect(): port must be 0-65535.
code de sortie : 1          (aucun site mesuré)
=== NOUVEAU code
vigie: site n°3 : adresse http ou https valide attendue (mal formée : Port out of range 0-65535), reçu 'https://example.com:99999'
code de sortie : 2
```

**Adresses étranges mais syntaxiquement valides**, glissées entre de vrais sites : chacune est notée `DOWN`, et tous les vrais sites sont mesurés.

```
UP   200    121 ms  Wikipédia (https://www.wikipedia.org)
UP   200     78 ms  GitHub (https://github.com)
DOWN ---     48 ms  Fantôme (https://site-fantome.invalid)  [[Errno -2] Name or service not known]
DOWN 403     81 ms  Port zéro (https://example.com:0/)
DOWN ---      3 ms  Points doubles (https://a..b.example/)  [[Errno -2] Name or service not known]
UP   200     94 ms  Debian (https://www.debian.org)
```

L'adresse au port 0 obtient une réponse 403 du serveur. Ce port n'a pas de sens, et on pourrait le refuser au chargement : piste notée, sans urgence, puisque le site est bien `DOWN`.

**Temps mesuré**, médiane de 3 passages sur les 5 sites de la configuration :

| Site | Corps entier (avant) | En-têtes seulement (après) |
|---|---|---|
| Wikipédia | 204 ms | 127 ms |
| GitHub | 143 ms | 89 ms |
| Debian | 177 ms | 96 ms |
| data.gouv.fr | 227 ms | 123 ms |
| Example | 83 ms | 79 ms |

### Limites connues

- Les adresses étranges mais valides (`a..b.example`, port 0) ne sont pas refusées au chargement. Elles donnent `DOWN`, sans planter.
- La règle « 5 erreurs imprévues de suite » est fixe dans le code. Elle n'a pas de raison d'être réglée tant qu'aucune erreur imprévue n'est connue.
- La version Bash de la sonde (étape 2) n'a pas reçu ces corrections : elle est gardée comme historique.

### Vocabulaire du lot

| Terme | Sens |
|---|---|
| Validation en entrée | Refuser une donnée invalide dès qu'elle arrive, avec un message clair, plutôt que de la laisser casser le programme plus loin |
| Filet de sécurité | Dernier recours qui attrape toute erreur imprévue pour limiter les dégâts, et la trace pour qu'on la corrige |
| Lecture en flux (*streaming*) | Lire une réponse au fur et à mesure, et pouvoir s'arrêter avant la fin |
| Garde-fou | Règle qui arrête un programme quand une erreur se répète, pour qu'elle ne passe pas inaperçue |
| Test rouge puis vert | Écrire le test, le voir échouer sur le code fautif, puis corriger jusqu'à ce qu'il passe |
| Régression | Défaut qui revient après avoir été corrigé ; un test qui le reproduit l'en empêche |

### Parcours du superviseur

Environ 30 minutes.

#### À lancer

```bash
cd ~/vigie && git switch main && git pull
make installer
make tests                     # 164 tests Python et 17 tests Bash
.venv/bin/vigie sonder         # les 5 sites de config/vigie.toml
```

#### À casser

1. Ouvre `config/vigie.toml` et remplace l'adresse de GitHub par `https://github.com:99999`.
2. Lance `.venv/bin/vigie sonder`, puis `echo $?`. Observe le message, qui désigne le site fautif, et le code de sortie 2.
3. Essaie aussi `https://git hub.com` (avec une espace), puis `http://[::1`.
4. Remets le fichier dans son état d'origine : `git checkout config/vigie.toml`.

#### Cinq questions

1. Pourquoi refuser une adresse mal écrite au chargement, plutôt que de la noter `DOWN` ?
   <details><summary>Réponse</summary>

   C'est une erreur de configuration, pas une panne du site. La noter `DOWN` enverrait une fausse alerte et ferait croire que le site est tombé. La refuser tout de suite, avec le numéro du site et la raison, permet de corriger en quelques secondes. Voir `probleme_url` dans `src/vigie/config.py`.
   </details>

2. Que se passe-t-il si une erreur imprévue survient en testant un site ?
   <details><summary>Réponse</summary>

   Le site est noté `DOWN` avec la cause « erreur interne (type) », la trace complète part dans le journal, et les autres sites sont mesurés normalement. Voir le dernier `except` de `sonder_site` dans `src/vigie/sonde.py`.
   </details>

3. Pourquoi `vigie surveiller` s'arrête-t-il après 5 erreurs imprévues de suite, au lieu de continuer ?
   <details><summary>Réponse</summary>

   Une erreur qui se répète cache un problème permanent. En s'arrêtant avec le code 1, la sonde laisse l'orchestrateur la relancer, et le nombre de redémarrages devient visible : `docker compose ps` aujourd'hui, l'état `CrashLoopBackOff` dans Kubernetes demain. Continuer en silence masquerait la panne.
   </details>

4. Pourquoi la sonde ne télécharge-t-elle plus le corps des pages, et quelle conséquence cela a-t-il ?
   <details><summary>Réponse</summary>

   Seul le code HTTP dit si un site répond. Télécharger la page coûtait du temps, de la mémoire et de la bande passante, et une adresse vers un gros fichier pouvait bloquer la sonde. Conséquence : le temps mesuré s'arrête à la réception des en-têtes. Il est plus court qu'avant, environ 35 à 45 % de moins sur les gros sites, et pas directement comparable. Le journal des versions le signale.
   </details>

5. Comment être sûr qu'un test détecte vraiment le défaut qu'il prétend couvrir ?
   <details><summary>Réponse</summary>

   En le voyant échouer sur le code fautif avant la correction. Ici, les 22 nouveaux tests ont été lancés contre le code d'avant le lot : les 22 échouent. Un test qui passait aussi sur l'ancien code a ainsi été repéré, puis renforcé.
   </details>

## Lot 8.2 : une page qui ne ment pas

### Le problème

Deux défauts trouvés à la revue du 10/11 :

- **Dans un conteneur, la page affichait les heures en UTC, sans le dire.** Vérifié : le conteneur indiquait 09:11 quand il était 10:11 à Paris. Un lecteur français se trompait d'une heure sur le début d'un incident.
- **Des données périmées s'affichaient en vert.** Si la sonde s'arrêtait, la page continuait d'afficher « Tous les sites répondent » avec la dernière mesure connue, même vieille de plusieurs heures. Une page de statut qui ment par omission, c'est pire que pas de page du tout.

### Ce qui a été fait

**1. Un fuseau horaire d'affichage réglable.** Dans `config/vigie.toml` : `[affichage] fuseau = "Europe/Paris"`. Un fuseau inconnu est refusé au chargement. La valeur par défaut est `UTC`, explicite et sans surprise. La page dit dans quel fuseau elle affiche, et chaque heure est aussi écrite dans une balise `<time datetime="…">` en UTC, lisible par une machine. La dépendance `tzdata` fournit la base des fuseaux, même dans une image qui n'en contient pas.

*Pourquoi régler le fuseau dans l'application plutôt que celui du conteneur ?* Le conteneur, les journaux et la base restent en UTC, ce qui est la règle en exploitation : une seule référence de temps, pas de piège au changement d'heure. Seul l'affichage destiné à un humain est converti.

**2. L'intervalle de la sonde entre dans la configuration.** `[sonde] intervalle = 300`. La sonde s'en sert pour rythmer ses passages, et l'API pour juger de la fraîcheur des mesures : les deux doivent donc partager la même valeur. Ordre de priorité : l'option `--intervalle`, puis la variable `VIGIE_INTERVALLE`, puis le fichier. `0` est désormais refusé.

**3. Les mesures périmées sont signalées.** Une mesure est périmée au-delà de **3 intervalles**, soit 15 minutes avec le réglage par défaut : la sonde a manqué au moins deux passages.
- `/api/sites` renvoie pour chaque site `age_secondes` et `perime`.
- La page affiche un **bandeau orange** : « Mesures périmées : dernière mesure il y a 47 min. La sonde ne tourne peut-être plus. »
- Un site périmé affiche « ? » avec son dernier état connu, au lieu d'un `UP` vert trompeur.
- Une vieille panne n'est plus présentée comme une panne actuelle. Une panne récente reste en rouge, en premier.

![Page de statut avec des mesures périmées](../images/page-perimee.jpg)

*Capture réelle, 16/11/2026 : un passage de sonde, puis la page servie avec un intervalle de 2 s. Au bout de 14 s sans nouvelle mesure, les 5 sites sont signalés. Avant le lot 8.2, cette même situation s'affichait en vert.*

**4. La sonde a un contrôle de santé.** `vigie sante-sonde` répond `0` si une mesure récente existe en base, `1` sinon. Il sert de contrôle de santé (`healthcheck`) au conteneur de la sonde. Avant, Docker savait seulement si le processus tournait. Il sait maintenant si la sonde **fait son travail** : une sonde qui tourne mais n'enregistre plus rien, par exemple parce que la base est injoignable, devient « unhealthy ».

### Les tests

**46 nouveaux tests** (210 au total, 99 % du code couvert). Lancés contre le code d'avant le lot, les 46 échouent. Pour être exact, beaucoup échouent simplement parce que les réglages `fuseau` et `intervalle` n'existaient pas encore.

Deux choix pour qu'ils prouvent vraiment quelque chose :

- **Les tests d'affichage utilisent le fuseau `Asia/Tokyo`.** S'ils utilisaient `Europe/Paris`, un affichage « à l'heure de la machine » passerait sur ce poste, qui est réglé sur Paris, et échouerait seulement dans la CI, qui est en UTC. Tokyo ne correspond à aucune des deux machines.
- **Un test sur la boucle de surveillance a dû être corrigé.** Il remplaçait l'objet `Event` de tout Python pour compter les attentes, et d'autres composants s'en servaient aussi pendant le test. Il ne remplace plus que celui de `vigie.cli`. Leçon : un remplacement trop large dans un test fausse le résultat.

**L'essai de bout en bout dans Docker** vérifie maintenant trois choses de plus :

1. la page annonce le fuseau `Europe/Paris` et affiche l'heure de Paris ;
2. la sonde est « healthy », devient « unhealthy » quand on arrête la base, puis redevient « healthy » quand la base revient ;
3. une fois la sonde arrêtée, la page passe au bandeau « Mesures périmées » et n'affiche plus de bandeau vert.

### Un réglage de l'essai corrigé en route

Au premier essai, la dernière mesure avait 13 s, alors que la sonde passait toutes les 5 s. L'examen des journaux montre des passages réguliers d'environ 0,3 s : l'écart vient d'un site qui a mis plusieurs secondes à répondre, ce qui est permis jusqu'au délai de 10 s. Avec un intervalle de 5 s, le seuil de péremption n'était que de 15 s : l'essai aurait pu échouer au hasard dans la CI. L'intervalle de l'essai passe à 10 s (seuil de 30 s). En production, avec 5 minutes d'intervalle, la marge est très large.

### Limites connues

- Le seuil de 3 intervalles est fixe dans le code.
- Le seuil ne tient pas compte du délai accordé à chaque site. C'est négligeable avec 5 minutes d'intervalle, mais à surveiller si on réduit beaucoup l'intervalle.
- La page s'actualise toute seule toutes les minutes, mais elle n'avertit pas activement : c'est le rôle de la supervision de la plateforme (étape 13, alerte « sonde muette »).

### Vocabulaire du lot

| Terme | Sens |
|---|---|
| Fuseau horaire | Règle qui donne l'heure locale à partir de l'heure universelle (UTC), changements d'heure compris |
| UTC | Temps universel coordonné : la référence unique, utilisée par les serveurs, les journaux et les bases |
| Donnée périmée | Donnée trop ancienne pour être crue, même si elle était juste au moment de sa mesure |
| Contrôle de santé (*healthcheck*) | Commande lancée régulièrement par Docker ou Kubernetes pour savoir si un service fonctionne vraiment |
| `healthy` / `unhealthy` | État que Docker attribue à un conteneur selon le résultat de son contrôle de santé |

### Parcours du superviseur

Environ 30 minutes.

#### À lancer

```bash
cd ~/vigie && git switch main && git pull
make installer && make tests
make docker-demarrer
make docker-etat             # attendre que « sonde » affiche (healthy)
```

Ouvre ensuite http://localhost:8000 : en bas de page, le fuseau `Europe/Paris` est annoncé, et les heures sont celles de ta montre.

#### À casser

1. Arrête la sonde : `docker compose stop sonde`.
2. Attends 15 minutes (3 intervalles de 5 minutes). Pour aller plus vite, mets `intervalle = 20` dans `config/vigie.toml`, relance avec `docker compose up -d`, attends une minute, puis arrête la sonde. La page passe au bandeau orange dans la minute.
3. Arrête la base : `docker compose stop base`. Après une minute ou deux, `make docker-etat` montre la sonde « unhealthy ». Relance avec `docker compose start base sonde`.
4. Remets tout en ordre : `git checkout config/vigie.toml`, puis `make docker-arreter`.

#### Cinq questions

1. Pourquoi garder le conteneur, les journaux et la base en UTC, et ne convertir que l'affichage ?
   <details><summary>Réponse</summary>

   Une seule référence de temps évite les erreurs de comparaison et les pièges du changement d'heure, par exemple l'heure qui existe deux fois fin octobre. On ne convertit qu'au dernier moment, pour un humain. Voir `zone` dans `src/vigie/api.py`.
   </details>

2. Qu'est-ce qu'une mesure « périmée », et pourquoi 3 intervalles ?
   <details><summary>Réponse</summary>

   Une mesure trop vieille pour être crue. Avec 1 intervalle, le moindre retard d'un passage déclencherait l'alerte. À 3, la sonde a manqué au moins deux passages : ce n'est plus un hasard. Voir `INTERVALLES_AVANT_PEREMPTION` dans `src/vigie/base.py`.
   </details>

3. Pourquoi l'API et la sonde doivent-elles connaître le même intervalle ?
   <details><summary>Réponse</summary>

   La sonde s'en sert pour rythmer ses passages, l'API pour juger la fraîcheur. Si l'API croyait à un intervalle de 5 minutes alors que la sonde passe toutes les heures, toutes les mesures paraîtraient périmées. D'où un seul réglage dans la configuration, et `VIGIE_INTERVALLE` transmis aux deux conteneurs dans `compose.yaml`.
   </details>

4. Quelle différence entre « le conteneur tourne » et « le conteneur est healthy » ?
   <details><summary>Réponse</summary>

   « Il tourne » veut seulement dire que le processus existe. « Healthy » veut dire que son contrôle de santé réussit, c'est-à-dire qu'il fait son travail. Une sonde qui ne peut plus écrire en base tourne toujours, mais n'est plus healthy. Kubernetes ira plus loin à l'étape 11 : il redémarrera ou retirera du trafic un pod en mauvaise santé.
   </details>

5. Pourquoi les tests d'affichage utilisent-ils le fuseau de Tokyo ?
   <details><summary>Réponse</summary>

   Pour ne coïncider avec aucune machine de test. Avec `Europe/Paris`, un code qui affiche l'heure de la machine passerait sur ce poste (réglé sur Paris) sans rien prouver.
   </details>

## Lot 8.3 : une base qui dure

### Le problème

Trois défauts trouvés à la revue du 10/11 :

- **Le schéma de la base n'avait pas de versions.** `schema.sql`, rejoué à chaque démarrage avec `IF NOT EXISTS`, ne savait que créer. Il ne pouvait ni modifier une colonne ni dire dans quel état se trouvait une base. Le lot 8.1 l'avait déjà poussé à sa limite pour ajouter une colonne.
- **La table des mesures grossissait sans limite** : une ligne par site toutes les 5 minutes, soit 1 440 lignes par jour pour 5 sites, pour toujours.
- **L'API ouvrait une connexion à la base pour chaque requête.** Ouvrir une connexion PostgreSQL coûte plusieurs millisecondes, et rien ne limitait leur nombre.

### Ce qui a été fait

**1. Des migrations numérotées.** Le schéma évolue désormais par fichiers SQL numérotés, dans [src/vigie/migrations/](../../src/vigie/migrations/) :

| Migration | Contenu |
|---|---|
| `0001_initial` | les tables `sondes` et `incidents` des versions 0.4 et 0.5 |
| `0002_motif_fin_incidents` | la colonne `motif_fin` ajoutée au lot 8.1 |
| `0003_index_date_sondes` | un index sur la date des mesures, pour la purge |

`vigie migrer` applique celles qui manquent, **chacune dans sa propre transaction**, et note dans la table `migrations` le numéro, le nom, la date et l'**empreinte** (SHA-256) de chaque fichier appliqué. Si un fichier déjà appliqué a changé, il refuse de continuer : on n'édite jamais une migration appliquée, on en écrit une nouvelle. `vigie init-db` reste accepté comme ancien nom, et le service Compose `init-db` devient `migrations`.

*Et les bases déjà créées par l'ancien `schema.sql` ?* Les deux premières migrations reprennent l'ancien schéma avec `IF NOT EXISTS`. Une ancienne base les passe sans erreur, puis reçoit la troisième comme une base neuve. Pourquoi un migrateur maison plutôt qu'Alembic : [décision 0006](../decisions/0006-migrateur-maison.md).

**2. Un verrou contre les lancements simultanés.** À l'étape 12, plusieurs copies de l'API démarreront en même temps, et chacune lancera les migrations. `vigie migrer` prend d'abord un **verrou consultatif** PostgreSQL (`pg_advisory_lock`) : le deuxième lancement attend que le premier ait fini, puis constate qu'il ne reste rien à faire. Le verrou est lié à la connexion : si le programme meurt en route, PostgreSQL le rend tout seul.

**3. La rétention des mesures.** `[retention] jours = 90` dans la configuration. `vigie surveiller` supprime **une fois par jour** les mesures plus vieilles, dès son premier passage. `vigie purger` fait la même chose à la demande. Les **incidents sont gardés** : ils sont peu nombreux et racontent l'historique des pannes. La suppression se fait par lots de 10 000 lignes, chacun dans une transaction courte. La purge attend un passage où la base répond, et réessaie au passage suivant si elle échoue.

**4. Un pool de connexions dans l'API.** L'API garde quelques connexions ouvertes, **5 au plus**, et les prête aux requêtes. Le pool s'ouvre au démarrage de l'application et se ferme à son arrêt. Ses connexions s'appellent `vigie-api` dans `pg_stat_activity`, la vue de PostgreSQL qui liste les connexions en cours : l'exploitant voit tout de suite qui les tient.

### Les tests

**54 nouveaux tests** (261 au total, 99 % du code couvert ; 100 % de chaque module sauf le petit point d'entrée `__main__.py`). Trois anciens tests de `schema.sql` disparaissent, remplacés par ceux des migrations.

Lancés contre le code d'avant le lot, **les 53 premiers échouent tous** : 27 en échec ou en erreur, et les 26 de `test_migrations.py` ne peuvent même pas se charger, puisque le module `migrateur` n'existait pas. Le 54e, et le renforcement d'un autre, viennent de l'essai de bout en bout (voir plus bas). Chacun a été vu échouer 3 fois sur 3 avant sa correction.

Ce que vérifient les tests des migrations, toujours sur un vrai PostgreSQL :

- une base vide reçoit tout le schéma, et relancer ne change rien, pas même les dates ;
- une base créée par **chacune des trois anciennes versions** de `schema.sql` (0.4, 0.5 et lot 8.1, conservées dans `tests/python/schemas-historiques/`) arrive exactement au même schéma qu'une base neuve, colonnes, contraintes et index compris, en gardant ses données ;
- 4 lancements simultanés réussissent tous, et chaque migration n'est appliquée qu'une fois ; pendant qu'un autre tient le verrou, `migrer` attend sans rien toucher ;
- deux `vigie migrer` lancés en même temps, comme deux vrais programmes, réussissent tous les deux ;
- une migration qui échoue est annulée en entier, les précédentes restent, et le verrou est rendu ;
- une migration modifiée après application est refusée ; une base en avance sur le code est signalée.

### Deux défauts du pool, trouvés par l'essai de bout en bout

Tous les tests passaient. L'essai dans Docker, lui, a échoué : **après le redémarrage de la base, la première requête à l'API recevait une erreur 503.** Avant le lot, sans pool, ce cas ne se posait pas : chaque requête ouvrait une connexion neuve.

**Première piste.** Pendant une panne, le pool réessaie de se connecter en espaçant ses essais : 1 s, 2 s, 4 s, 8 s… pendant 5 minutes par défaut. La base revenue, l'API pouvait donc rester en erreur jusqu'au prochain essai, parfois plusieurs minutes. Un test l'a reproduit (une base qui n'existe pas, puis qu'on crée) : **3 échecs sur 3**. Correction : le pool abandonne au bout du temps d'attente d'une requête, et la requête suivante relance aussitôt un essai. Le test passe… mais l'essai Docker échouait encore.

**La vraie cause, trouvée dans les journaux horodatés.** Pendant la panne, l'API n'avait tenté **aucune** connexion. Au retour de la base, le pool tenait 5 connexions mortes en réserve. Avant de prêter une connexion, il la vérifie, et s'il tombe sur une connexion morte, il **patiente avant d'essayer la suivante** (1 s, puis 2 s), pour ne pas tourner en boucle. Avec 3 s d'attente au plus, la requête n'atteignait jamais les connexions neuves. Un test l'a reproduit (5 connexions en réserve, toutes coupées) : **3 échecs sur 3**. Correction : à la première connexion morte, le pool vérifie d'un coup toutes celles qui attendent en réserve.

Résultat : l'essai Docker passe **3 fois sur 3**, et `/api/sites` répond du premier coup après le redémarrage de la base, en 0,03 s.

**Leçons :** des tests unitaires ne remplacent pas un essai dans des conditions réelles, ici une vraie base qu'on arrête. Et une première explication plausible peut être juste sans être **la** cause : seules les mesures horodatées l'ont montré.

### Essais réels

**Mise à niveau d'une base créée par l'image 0.5 publiée** (`ghcr.io/lamajoker/vigie:e77e6d6`), dans des conteneurs jetables :

```
=== 1. Base créée par l'image publiée ghcr.io/lamajoker/vigie:e77e6d6 (vigie 0.5.0)
Base de données prête.
=== 2. Mise à niveau par l'image du lot 8.3
Migration appliquée : 0001_initial
Migration appliquée : 0002_motif_fin_incidents
Migration appliquée : 0003_index_date_sondes
Base de données à jour (version 3).
=== 4. Relance sur la base mise à niveau
Base de données déjà à jour (version 3).
=== 5. Comparaison des schémas (pg_dump --schema-only)
schémas identiques (73 lignes)
mesure gardée : 1 ligne(s) dans sondes
```

**Deux `migrer` lancés en même temps** sur une base vide, dans deux conteneurs : l'un applique les trois migrations, l'autre attend puis répond « Base de données déjà à jour (version 3) ». La table `migrations` contient 3 lignes, pas 6.

**La base de développement de ce poste**, créée à l'étape 4 par l'ancien `schema.sql`, a été mise à niveau le 16/11 par `make db-demarrer` : 3 migrations notées, et ses 30 mesures du 9 au 16 novembre conservées.

**Connexions à la base sous 50 requêtes simultanées**, chaque lecture étant ralentie à 0,1 s pour que les requêtes se chevauchent vraiment :

| | Connexions simultanées au plus | Durée des 50 requêtes |
|---|---|---|
| Avant le lot (une connexion par requête) | 40 | 0,48 s |
| Avec le pool | 5 | 1,23 s |

Avant le lot, seul le nombre de fils d'exécution du serveur (40) limitait le nombre de connexions. Avec le pool, il ne dépasse jamais 5. La contrepartie est visible : avec des lectures artificiellement lentes, les requêtes font la queue. En temps normal, une lecture prend quelques millisecondes et la file ne se voit pas. L'essai Docker le vérifie aussi avec 50 vraies requêtes `curl` simultanées : 5 connexions ouvertes après la rafale.

### Limites connues

- Pas de retour en arrière automatique d'une migration : on corrige par une nouvelle migration.
- La migration 0003 crée son index sans l'option `CONCURRENTLY`. Sur une très grosse table, cela bloquerait les écritures le temps de la création. Ici, avec 90 jours de rétention et 5 sites, la table ne dépasse pas 130 000 lignes.
- La taille du pool (5) est fixe dans le code. Avec plusieurs copies de l'API (étape 12), le total, nombre de copies × 5, devra rester sous la limite de PostgreSQL (100 connexions par défaut).
- Pendant une panne de la base, chaque essai de reconnexion du pool écrit un avertissement dans le journal de l'API.
- La rétention vaut pour tous les sites à la fois.

### Vocabulaire du lot

| Terme | Sens |
|---|---|
| Migration | Fichier qui fait évoluer le schéma de la base d'une étape, appliqué une seule fois et dans l'ordre |
| Empreinte (*hash*) | Résumé d'un fichier calculé par une fonction comme SHA-256 : si le fichier change d'un seul caractère, l'empreinte change |
| Verrou consultatif (*advisory lock*) | Verrou nommé par un nombre, que les programmes s'accordent à respecter ; PostgreSQL ne le pose sur aucune table |
| Rétention | Durée pendant laquelle on garde des données avant de les supprimer |
| Pool de connexions | Réserve de connexions ouvertes, prêtées aux requêtes puis rendues, au lieu d'en ouvrir une à chaque fois |
| `pg_stat_activity` | Vue de PostgreSQL qui liste les connexions en cours et ce qu'elles font |
| Attente exponentielle (*backoff*) | Espacer de plus en plus ses nouveaux essais (1 s, 2 s, 4 s…) pour ne pas harceler un service en panne |

### Parcours du superviseur

Environ 30 minutes.

#### À lancer

```bash
cd ~/vigie && git switch main && git pull
make installer && make tests
make db-demarrer             # met aussi à niveau ta base de développement
psql -h "$PWD/.pgdata" -p 5433 -U vigie -d vigie -c 'SELECT * FROM migrations'
```

#### À casser

1. Ajoute une ligne de commentaire, par exemple `-- essai`, à la fin de `src/vigie/migrations/0003_index_date_sondes.sql`.
2. Lance `.venv/bin/vigie migrer --base "postgresql://vigie@/vigie?host=$PWD/.pgdata&port=5433"`, puis `echo $?` : la migration modifiée est refusée, avec le code 2.
3. Remets le fichier en état : `git checkout src/vigie/migrations/`, puis `make db-arreter`.
4. Lance la pile : `make docker-demarrer`. Envoie 50 requêtes en même temps : `seq 50 | xargs -P 50 -I{} curl -s -o /dev/null http://localhost:8000/api/sites`. Compte les connexions de l'API : `docker compose exec base psql -U vigie -d vigie -c "SELECT count(*) FROM pg_stat_activity WHERE application_name = 'vigie-api'"`. Il y en a 5 au plus.
5. Lance deux migrations en même temps : `docker compose run --rm migrations & docker compose run --rm migrations & wait`. Les deux réussissent. Puis `make docker-arreter`.

#### Cinq questions

1. Pourquoi numéroter les migrations et noter dans la base celles qui sont appliquées, plutôt que rejouer un schéma complet ?
   <details><summary>Réponse</summary>

   Un schéma rejoué avec `IF NOT EXISTS` ne sait que créer : il ne peut ni modifier une colonne, ni dire où en est une base. Avec des migrations numérotées et la table `migrations`, chaque base sait exactement quelles étapes elle a reçues, et chacune n'est appliquée qu'une fois. Voir `src/vigie/migrateur.py`.
   </details>

2. Que se passe-t-il si deux conteneurs lancent `vigie migrer` en même temps ?
   <details><summary>Réponse</summary>

   Le premier prend le verrou consultatif `pg_advisory_lock`. Le second attend, puis constate que tout est déjà appliqué et répond « déjà à jour ». Sans verrou, les deux pourraient appliquer la même migration et l'un échouerait. Voir `CLE_VERROU` dans `src/vigie/migrateur.py`.
   </details>

3. Pourquoi refuser de continuer si une migration déjà appliquée a été modifiée ?
   <details><summary>Réponse</summary>

   Les bases qui l'ont déjà reçue ne verront jamais la modification : elles divergeraient en silence de celles créées après. L'empreinte SHA-256 de chaque fichier, notée à l'application, permet de le détecter. La bonne pratique : écrire une nouvelle migration.
   </details>

4. Pourquoi supprimer les vieilles mesures par lots, et pourquoi garder les incidents ?
   <details><summary>Réponse</summary>

   Une très longue transaction retarde le nettoyage automatique de PostgreSQL (autovacuum) sur toute la base : des lots de 10 000 lignes gardent chaque transaction courte. Les incidents, eux, sont peu nombreux et racontent l'historique des pannes : on les garde. Voir `purger` dans `src/vigie/base.py`.
   </details>

5. À quoi sert un pool de connexions, et quel piège l'essai de bout en bout a-t-il révélé ?
   <details><summary>Réponse</summary>

   Il évite d'ouvrir une connexion à chaque requête et borne leur nombre : 5 au lieu de 40 sous 50 requêtes simultanées. Le piège : après un redémarrage de la base, ses connexions en réserve sont mortes. Le pool les vérifiait une à une en patientant entre chaque, et la requête finissait en 503. Désormais, à la première connexion morte, il les vérifie toutes d'un coup. Voir `creer_pool` dans `src/vigie/base.py`.
   </details>

## Lot 8.4 : une construction reproductible

### Le problème

Défaut 9 de la revue du 10/11 : **la construction n'était pas reproductible.** Tout ce qu'elle téléchargeait était désigné par une étiquette qui peut changer de contenu :

- les dépendances Python par des bornes (`fastapi>=0.115`), résolues le jour de la construction ;
- les images Docker par une étiquette (`python:3.14-slim`, `postgres:18-alpine`, `hadolint/hadolint:latest-debian`) ;
- les actions GitHub par une version majeure (`actions/checkout@v5`).

Le même commit pouvait donc donner deux images différentes à une semaine d'écart. Et une étiquette déplacée par un attaquant aurait fait exécuter son code dans la CI : c'est arrivé en mars 2025 à l'action `tj-actions/changed-files`, dont les étiquettes ont été redirigées vers un code qui recopiait les secrets dans les journaux.

### Ce qui a été fait

**1. Les dépendances Python sont verrouillées avec uv.** `uv.lock` donne la version exacte et l'empreinte SHA-256 de chacun des 33 paquets, soit 425 empreintes : une par fichier publié, pour chaque système et chaque version de Python. Le verrou est **universel** : le même fichier vaut pour Python 3.12 à 3.14. `make installer`, la CI et le Dockerfile installent tous avec `uv sync --locked` :

- `--locked` refuse un verrou qui ne correspond plus à `pyproject.toml` ;
- uv refuse tout paquet téléchargé dont l'empreinte diffère de celle du verrou.

`make verrouiller` recalcule le verrou après une modification de `pyproject.toml`.

**2. L'outil de construction du paquet est figé lui aussi.** Avec setuptools, construire Vigie téléchargeait setuptools, sans empreinte, à chaque construction. Le projet passe à `uv_build`, intégré à uv : vérifié sur une copie, uv construit le paquet sans rien télécharger (« Using bundled `uv_build` backend »). Les migrations SQL et la page HTML sont bien dans le paquet.

**3. uv a une version fixée partout.** `required-version = "==0.13.8"` dans `pyproject.toml` : uv refuse de travailler à une autre version, et l'action `setup-uv` de la CI lit cette valeur. Sur le poste, `scripts/installer-uv.sh` télécharge l'archive officielle et vérifie son empreinte, écrite dans le script, avant de l'extraire. Pas de `curl | sh`. L'empreinte a été recoupée entre l'API de GitHub et le fichier publié par Astral, l'éditeur de uv.

**4. Images et actions sont désignées par leur empreinte.**

| Quoi | Avant | Après |
|---|---|---|
| Images du Dockerfile | `python:3.14-slim` | `python:3.14-slim@sha256:9aaa47…`, et l'image de uv de même |
| Base de `compose.yaml` | `postgres:18-alpine` | `postgres:18-alpine@sha256:b6972e…` |
| hadolint, actionlint | `latest` | version précise et empreinte, une seule fois dans le Makefile |
| Actions GitHub | `actions/checkout@v5` | `actions/checkout@3d3c42e…  # v7.0.1` |

Au passage, les actions passent à leurs versions sur Node.js 24 : GitHub signalait que Node.js 20, abandonné, tournait encore. `astral-sh/setup-uv` remplace `actions/setup-python` : il installe uv et Python, ce qui fait une action de moins à surveiller.

**5. Un contrôle automatique.** `scripts/verifier_epinglage.py`, lancé par `make lint` et la CI, lit le Dockerfile, `compose.yaml`, le Makefile, les workflows et les scripts. Il refuse toute action sans SHA de commit complet et sa version en commentaire, toute image sans empreinte, et un dépôt sans `uv.lock`.

**6. Dependabot.** Chaque lundi, il propose par pull request les nouvelles versions des dépendances Python, des images et des actions. Les mises à jour mineures d'un même écosystème sont groupées. Une version doit avoir 7 jours avant d'être proposée, car une version piégée est souvent repérée et retirée dans les premiers jours. Il y a 5 pull requests ouvertes au plus. Pourquoi tout épingler, et pourquoi uv : [décision 0007](../decisions/0007-tout-epingler-par-empreinte.md).

### Les tests

**26 nouveaux tests** (287 au total). Lancé sur le dépôt d'avant le lot, le contrôle trouve **16 références sans empreinte**, plus l'absence de verrou :

```
uv.lock absent : les dépendances Python ne sont pas verrouillées
Dockerfile, ligne 1 : syntaxe sans empreinte : docker/dockerfile:1
Dockerfile, ligne 10 : image désignée par une variable : python:${PYTHON_VERSION}-slim
compose.yaml, ligne 36 : image sans empreinte : postgres:18-alpine
Makefile, ligne 115 : image sans empreinte : hadolint/hadolint:latest-debian
.github/workflows/ci.yml, ligne 39 : action non épinglée par un SHA de commit complet : actions/checkout@v5
…
16 problème(s) d'épinglage
```

Les 5 tests qui portent sur le dépôt échouaient : dépôt entièrement épinglé, Dockerfile et CI qui installent depuis le verrou, construction sans téléchargement. Les 21 autres vérifient le contrôle lui-même sur des exemples, bons et mauvais.

### Essais réels

**Deux constructions de l'image, sans cache, à quelques minutes d'écart :** mêmes 24 paquets aux mêmes versions (`pip freeze` identique), par exemple `fastapi==0.163.1`, `httpx==0.28.1`, `psycopg==3.3.9`. L'image passe de 249 à 231 Mo ; entre autres, l'environnement de Vigie ne contient plus pip, inutile à l'exécution.

**Une empreinte altérée dans une copie du verrou.** Premier essai : j'ai modifié la première empreinte trouvée pour httpx… et la construction a réussi. Explication : c'était l'empreinte de l'archive source (`.tar.gz`), que uv ne télécharge jamais puisqu'il prend le paquet précompilé (`.whl`). Second essai, sur l'empreinte du paquet réellement téléchargé :

```
error: Failed to download `httpx==0.28.1`
  cause: Hash mismatch for `httpx==0.28.1`
         Expected:
           sha256:d909fcccc110f8c7faf814ca82a9a4d816bc5a6dbfea25d6591d6985b8ba59a0
         Computed:
           sha256:d909fcccc110f8c7faf814ca82a9a4d816bc5a6dbfea25d6591d6985b8ba59ad
ERROR: failed to build
```

La construction s'arrête : un paquet qui ne correspond pas exactement au verrou n'entre pas dans l'image. **Leçon :** un essai qui réussit quand il devrait échouer mérite qu'on comprenne pourquoi avant de conclure.

**L'essai de bout en bout** (`make ci`) passe avec la nouvelle image et les nouveaux workflows, et actionlint valide les workflows.

### Limites connues

- Restent hors du verrou : les paquets système installés par `apt` dans la CI (bats, ShellCheck), les programmes préinstallés sur les machines de GitHub (PostgreSQL pour les tests), et ces machines elles-mêmes (`ubuntu-24.04` évolue chaque semaine).
- Dependabot ne met pas à jour les images du Makefile (hadolint, actionlint) ni la version de uv dans `scripts/installer-uv.sh` et `required-version`. Ces trois-là se changent à la main. Si Dependabot propose seul une nouvelle image de uv, la CI échouera sur `required-version`, ce qui empêche de mélanger deux versions de uv.
- Docker Hub limite les téléchargements anonymes. Avec 3 images par passage de CI, la limite est loin. Un miroir sera à prévoir si le rythme augmente.
- La première vague de Dependabot arrivera le lundi suivant la fusion. Les pull requests ouvertes ce jour-là donneront une idée du rythme réel des mises à jour.

### Vocabulaire du lot

| Terme | Sens |
|---|---|
| Construction reproductible | Le même code source donne le même résultat, quel que soit le jour de la construction |
| Verrou (*lockfile*) | Fichier qui fige la version exacte et l'empreinte de chaque dépendance, y compris les dépendances des dépendances |
| Verrou universel | Un seul verrou valable pour toutes les versions de Python et tous les systèmes acceptés |
| Épingler | Désigner une dépendance par son contenu exact (empreinte, SHA) plutôt que par un nom qui peut changer |
| Étiquette mobile | Nom (`v5`, `latest`, `3.14-slim`) qu'on peut faire pointer vers un autre contenu |
| Attaque de la chaîne d'approvisionnement | Attaque qui passe par une dépendance ou un outil de construction plutôt que par le code du projet |
| Wheel | Paquet Python précompilé (`.whl`), prêt à installer, par opposition à l'archive source |

### Parcours du superviseur

Environ 30 minutes.

#### À lancer

```bash
cd ~/vigie && git switch main && git pull
scripts/installer-uv.sh      # rien à faire si uv 0.13.8 est déjà là
make installer && make tests
make lint                    # dernière ligne : le contrôle d'épinglage
```

Ouvre `uv.lock` et cherche `name = "httpx"` : version exacte, adresse de chaque fichier, et son empreinte.

#### À casser

1. Dans le `Dockerfile`, supprime `@sha256:…` de la première ligne `FROM python:…`. Lance `.venv/bin/python scripts/verifier_epinglage.py` : la ligne est refusée. Remets le fichier : `git checkout Dockerfile`.
2. Altère l'empreinte du paquet httpx : `sed -i 's/6985b8ba59ad/6985b8ba59a0/' uv.lock`, puis `docker build -t vigie:essai .`. La construction s'arrête sur `Hash mismatch`. Si httpx a changé de version depuis, prends la fin de l'empreinte de sa ligne `.whl` dans `uv.lock`. Remets le fichier : `git checkout uv.lock`.
3. Dans `pyproject.toml`, change `"jinja2>=3.1,<4"` en `"jinja2>=3.1.6,<4"`, puis `make installer` : uv refuse, parce que le verrou ne correspond plus. `make verrouiller` le recalcule. Remets tout : `git checkout pyproject.toml uv.lock`.

#### Cinq questions

1. Pourquoi une étiquette comme `v5` ou `3.14-slim` ne suffit-elle pas ?
   <details><summary>Réponse</summary>

   Une étiquette est un nom qui pointe vers un contenu, et on peut la déplacer. En mars 2025, les étiquettes de l'action `tj-actions/changed-files` ont été redirigées vers un code malveillant, exécuté par tous les dépôts qui les utilisaient. Un SHA de commit ou une empreinte d'image désigne un contenu exact, qui ne peut pas changer. Voir la décision 0007.
   </details>

2. Que contient `uv.lock` que `pyproject.toml` ne contient pas ?
   <details><summary>Réponse</summary>

   `pyproject.toml` donne des bornes (`fastapi>=0.115`). `uv.lock` donne la version exacte de chaque paquet, dépendances des dépendances comprises, et l'empreinte de chaque fichier. Il est universel : le même fichier sert pour Python 3.12 et 3.14.
   </details>

3. Que se passe-t-il si un paquet téléchargé ne correspond pas à son empreinte ?
   <details><summary>Réponse</summary>

   uv refuse de l'installer et la construction échoue (« Hash mismatch »). C'est ce qui protège contre un fichier remplacé sur le registre ou modifié en route. Essai dans la partie « Essais réels ».
   </details>

4. Pourquoi la première empreinte altérée n'a-t-elle pas fait échouer la construction ?
   <details><summary>Réponse</summary>

   C'était celle de l'archive source de httpx, que uv ne télécharge jamais : il installe le paquet précompilé (wheel), qui a sa propre empreinte. Un essai qui réussit quand on attend un échec doit être compris avant de conclure.
   </details>

5. Si tout est figé, comment le projet reçoit-il les correctifs de sécurité ?
   <details><summary>Réponse</summary>

   Par Dependabot : chaque lundi, il propose les nouvelles versions en pull request, testées par la CI. On les fusionne, et chaque mise à jour reste visible et réversible. Le délai de 7 jours laisse le temps de repérer une version piégée. Voir `.github/dependabot.yml`.
   </details>

## Temps de supervision

Rempli par le superviseur.

| Jour | Activité | Durée |
|---|---|---|
| | | |

**Total :** h
