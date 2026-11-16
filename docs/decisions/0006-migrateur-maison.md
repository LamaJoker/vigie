# 0006. Un petit migrateur maison plutôt qu'Alembic

- **Statut :** acceptée
- **Date :** 2026-11-16

## Contexte

Jusqu'au lot 8.2, le schéma de la base tenait dans un seul fichier, `schema.sql`, rejoué à chaque démarrage grâce à `CREATE TABLE IF NOT EXISTS`. Ce procédé ne sait que créer : il ne peut ni modifier une colonne, ni dire dans quel état se trouve une base. Le lot 8.1 l'a déjà poussé à sa limite en ajoutant une colonne par `ADD COLUMN IF NOT EXISTS`.

Or Vigie va être déployée sur des serveurs (étape 10) puis dans Kubernetes (étape 12), avec plusieurs copies de l'API qui démarrent en même temps. Il faut donc :

- faire évoluer le schéma par étapes numérotées, appliquées une seule fois chacune ;
- savoir, en regardant une base, quelles étapes elle a reçues ;
- supporter plusieurs lancements simultanés sans qu'ils se marchent dessus ;
- mettre à niveau les bases déjà créées par l'ancien `schema.sql`.

## Décision

Un migrateur d'environ 150 lignes, commentaires compris : [src/vigie/migrateur.py](../../src/vigie/migrateur.py), et la commande `vigie migrer`.

- **Un fichier SQL par étape**, numéroté sans trou : `src/vigie/migrations/0001_initial.sql`, `0002_…`. Un trou, un doublon ou un nom mal formé arrête tout.
- **Une table `migrations`** retient chaque étape appliquée, avec la date et l'empreinte SHA-256 du fichier. Si un fichier déjà appliqué a changé, le migrateur refuse de continuer : on n'édite jamais une migration appliquée, on en écrit une nouvelle.
- **Une transaction par migration** : une migration qui échoue est annulée en entier, et les précédentes restent acquises.
- **Un verrou consultatif PostgreSQL** (`pg_advisory_lock`) entoure le tout. Un deuxième lancement attend que le premier ait fini, puis constate qu'il ne reste rien à faire. Le verrou est lié à la connexion : si le programme meurt, PostgreSQL le rend.
- **Adoption des bases existantes** : les deux premières migrations reprennent l'ancien schéma avec `IF NOT EXISTS`. Une base créée par l'ancien `schema.sql` passe ces deux étapes sans erreur, puis reçoit les suivantes comme une base neuve. Les migrations suivantes n'ont pas besoin de cette précaution.
- **Une base en avance sur le code** (après un retour à une version précédente de Vigie) est signalée, mais n'est pas bloquante : c'est à chaque migration de rester compatible avec le code de la version d'avant (ajouter avant de retirer).
- `vigie init-db` reste accepté comme ancien nom de `vigie migrer`.

## Conséquences

- Le schéma a maintenant une version, lisible dans la base : `SELECT * FROM migrations`.
- Le lancement des migrations est sûr avec plusieurs copies de l'API. Dans Kubernetes, il pourra se faire dans un conteneur d'initialisation de chaque copie.
- Il n'y a pas de retour en arrière automatique (« downgrade ») : on corrige par une nouvelle migration. C'est aussi la pratique recommandée avec les outils du marché, parce qu'un retour en arrière détruit souvent des données.
- C'est du code à maintenir. Il est petit et couvert par des tests sur un vrai PostgreSQL : base vide, bases créées par les trois anciennes versions de `schema.sql`, lancements simultanés, migration qui échoue, fichier modifié.

## Solutions écartées

- **Alembic** : l'outil de référence en Python, mais il est construit sur SQLAlchemy, qu'il faudrait ajouter alors que le projet interroge PostgreSQL en SQL direct ([décision 0002](0002-postgresql-et-sql-direct.md)). Ses migrations s'écrivent en Python plutôt qu'en SQL.
- **Flyway, Liquibase** : solides et très répandus, mais écrits en Java. Il faudrait une JVM ou une image de plus pour trois fichiers SQL.
- **sqitch, dbmate** : bons outils centrés sur le SQL, mais un binaire de plus à installer et à épingler dans l'image, pour un besoin qu'une centaine de lignes couvre.
- **Garder `schema.sql` et `IF NOT EXISTS`** : ne sait ni modifier ni versionner, comme expliqué plus haut.
