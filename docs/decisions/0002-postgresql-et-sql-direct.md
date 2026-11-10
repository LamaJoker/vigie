# 0002. PostgreSQL, interrogé en SQL direct, sans ORM

- **Statut :** acceptée
- **Date :** 2026-11-09 (écrite le 2026-11-10)

## Contexte

À l'étape 4, les résultats de la sonde devaient quitter un simple fichier pour une base de données, afin de calculer une disponibilité, d'afficher une page de statut et, plus tard, de garder l'état des incidents.

## Décision

- **PostgreSQL**, la base relationnelle libre la plus répandue en entreprise.
- **Requêtes SQL écrites à la main**, envoyées par le pilote `psycopg`, toujours **paramétrées** (jamais de valeur collée dans le texte SQL).
- **Les règles importantes sont tenues par la base elle-même** : contraintes `CHECK` sur les états et les codes HTTP, index unique partiel qui garantit un seul incident ouvert par site.
- **En développement et en test, PostgreSQL est lancé à la demande** : base de développement dans `.pgdata/` (sans port réseau), base jetable créée par les tests. Aucune base ne tourne en permanence sur le poste.

## Conséquences

- Le SQL est visible et lisible, ce qui est utile pour apprendre et pour expliquer.
- Les tests tournent contre un vrai PostgreSQL, pas contre une imitation : ce qui passe en test passe en production.
- Il n'y a pas d'outil de migrations : le schéma ne sait que se créer. C'est corrigé au lot 8.3 par un petit migrateur.

## Solutions écartées

- **SQLite** : plus simple, mais éloigné de ce qu'on exploite en entreprise, et faible pour les accès concurrents de la sonde et de l'API.
- **Un ORM (SQLAlchemy)** : utile sur un gros modèle de données, superflu pour deux tables, et il cache le SQL qu'on veut justement montrer.
