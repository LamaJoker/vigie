# Vigie

> Service de surveillance de sites web : il vérifie régulièrement que des sites répondent, garde l'historique de leurs temps de réponse, publie une page de statut et envoie une alerte quand un site tombe.

**Statut : en construction (semaine 1 sur 14).**

## Pourquoi ce projet

Vigie est mon projet de formation au métier de DevOps. L'application est volontairement simple : l'essentiel du travail porte sur la chaîne qui la construit, la teste, la déploie et la supervise, comme en entreprise.

## Méthode de travail

Le projet est réalisé avec un assistant IA de programmation (Claude, d'Anthropic), que je supervise :

- je fixe les objectifs de chaque étape et je valide les choix techniques ;
- l'assistant réalise le travail et propose chaque changement dans une pull request, avec ses explications ;
- je relis, je pose mes questions et je décide de fusionner ou non.

Les commits écrits par l'assistant portent la mention `Co-Authored-By: Claude`.

## Suivre l'évolution

- La [feuille de route](ROADMAP.md) liste les 14 étapes et ce qui est terminé.
- Un [compte rendu par semaine](docs/semaines/) explique ce qui a été fait, pourquoi, comment le vérifier, et le temps passé.
- Les [pull requests](https://github.com/LamaJoker/vigie/pulls?q=is%3Apr) montrent chaque changement et sa validation.

## Ce que Vigie fera

- Tester une liste de sites à intervalle régulier (code HTTP, temps de réponse).
- Enregistrer les résultats dans une base de données.
- Afficher une page de statut : sites en ligne, incidents en cours, historique.
- Envoyer une alerte (Discord, e-mail) quand un site ne répond plus, puis quand il revient.

## Compétences travaillées

| Domaine | Outils |
|---|---|
| Système | Linux (Ubuntu sous WSL2), Bash |
| Code | Python, FastAPI, PostgreSQL, pytest |
| Conteneurs | Docker, Docker Compose |
| Intégration et déploiement continus | GitHub Actions |
| Sécurité | Trivy, Dependabot, gestion des secrets |
| Infrastructure as code | Terraform, Ansible |
| Orchestration | Kubernetes (k3d), Helm, Argo CD |
| Supervision | Prometheus, Grafana, Loki |

## Organisation du dépôt

```
vigie/
├── README.md        ce fichier
├── ROADMAP.md       feuille de route sur 14 semaines
├── .github/         modèle de pull request
└── docs/
    └── semaines/    un compte rendu par semaine
```

## Conventions

Chaque changement passe par une branche et une pull request avant d'arriver sur `main`.

Les messages de commit suivent le format [Conventional Commits](https://www.conventionalcommits.org/fr/v1.0.0/) :

| Préfixe | Usage |
|---|---|
| `feat:` | nouvelle fonctionnalité |
| `fix:` | correction d'un bug |
| `docs:` | documentation, comptes rendus |
| `test:` | tests |
| `ci:` | intégration continue |
| `chore:` | maintenance (dépendances, configuration) |

Exemple : `docs: compte rendu de la semaine 1`
