# Vigie

> Service de surveillance de sites web : il vérifie régulièrement que des sites répondent, garde l'historique de leurs temps de réponse, publie une page de statut et envoie une alerte quand un site tombe.

**Statut : en construction (semaine 1 sur 14).**

## Pourquoi ce projet

Vigie est mon projet de formation au métier de DevOps. L'application est volontairement simple : l'essentiel du travail porte sur la chaîne qui la construit, la teste, la déploie et la supervise, comme en entreprise.

L'évolution se suit semaine après semaine :

- la [feuille de route](ROADMAP.md) liste les 14 étapes et ce qui est terminé ;
- le [journal de bord](docs/journal/) raconte chaque semaine : ce que j'ai fait, ce que j'ai appris, ce qui a coincé et le temps passé ;
- l'historique des commits et des pull requests montre le travail au fil de l'eau.

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
└── docs/
    ├── guides/      instructions de chaque semaine
    └── journal/     journal de bord hebdomadaire
```

## Conventions

Les messages de commit suivent le format [Conventional Commits](https://www.conventionalcommits.org/fr/v1.0.0/) :

| Préfixe | Usage |
|---|---|
| `feat:` | nouvelle fonctionnalité |
| `fix:` | correction d'un bug |
| `docs:` | documentation, journal |
| `test:` | tests |
| `ci:` | intégration continue |
| `chore:` | maintenance (dépendances, configuration) |

Exemple : `docs: journal de la semaine 1`
