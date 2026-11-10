# Décisions d'architecture

Chaque choix structurant du projet est écrit ici, au moment où il est fait : le contexte, la décision, ses conséquences et les solutions écartées. Six mois plus tard, on sait encore **pourquoi** le projet est comme il est. On appelle souvent ce format « ADR » (*Architecture Decision Record*).

Une décision n'est jamais réécrite. Si elle change, une nouvelle décision la remplace et l'ancienne passe au statut « remplacée ».

| N° | Décision | Statut |
|---|---|---|
| [0001](0001-methode-assistant-ia-supervise.md) | Le projet est réalisé par un assistant IA, supervisé | Acceptée |
| [0002](0002-postgresql-et-sql-direct.md) | PostgreSQL, interrogé en SQL direct, sans ORM | Acceptée |
| [0003](0003-une-alerte-au-debut-une-a-la-fin.md) | Une alerte au début d'un incident, une à la fin, rien entre les deux | Acceptée |
| [0004](0004-conteneurs-sans-root-lecture-seule.md) | Conteneurs sans root, en lecture seule, sans capacités Linux | Acceptée |
| [0005](0005-tout-en-local-sans-frais.md) | Tout en local, pour 0 € : Incus et k3d plutôt qu'un cloud | Acceptée |

## Modèle

```markdown
# NNNN. Titre court

- **Statut :** proposée | acceptée | remplacée par NNNN
- **Date :** AAAA-MM-JJ

## Contexte
Le problème, les contraintes.

## Décision
Ce qu'on fait.

## Conséquences
Ce que ça apporte, ce que ça coûte.

## Solutions écartées
Et pourquoi.
```
