# Architecture

## Aujourd'hui (étape 7)

Vigie tourne en conteneurs sur le poste de développement, avec Docker Compose. Chaque modification passe par GitHub Actions, qui teste puis publie l'image.

```mermaid
flowchart LR
    subgraph poste["Poste : WSL2 et Docker Compose"]
        sonde["sonde<br/>vigie surveiller"]
        api["api<br/>page de statut et API"]
        initdb["init-db<br/>crée les tables"]
        base[("base<br/>PostgreSQL 18")]
    end
    sites["Sites surveillés"]
    discord["Discord"]
    navigateur["Navigateur"]

    sonde -->|"HTTP, toutes les 5 min"| sites
    sonde -->|"mesures, incidents"| base
    sonde -->|"alertes"| discord
    initdb --> base
    api -->|"lecture"| base
    navigateur -->|"127.0.0.1:8000"| api

    subgraph github["GitHub"]
        depot["Dépôt"]
        ci["GitHub Actions<br/>style, tests, essai complet"]
        ghcr["ghcr.io/lamajoker/vigie"]
    end
    depot --> ci -->|"image testée, sur main"| ghcr
```

| Élément | Rôle | Exposition |
|---|---|---|
| `sonde` | teste les sites, enregistre les mesures, ouvre et ferme les incidents, envoie les alertes | aucune |
| `api` | page de statut, API JSON, point de contrôle `/sante` | `127.0.0.1:8000` seulement |
| `init-db` | crée les tables puis s'arrête | aucune |
| `base` | PostgreSQL 18, données dans un volume | aucune, réseau interne seulement |

## Cible (étape 14)

La même application, déployée de deux façons pour couvrir les deux mondes de l'exploitation : des serveurs configurés par Ansible, et un cluster Kubernetes piloté par Git.

```mermaid
flowchart TB
    pr["Pull request"] --> ci["GitHub Actions<br/>tests, analyse de sécurité"]
    ci -->|"version publiée, signée"| ghcr["ghcr.io"]

    subgraph serveurs["Serveurs Incus : créés par Terraform, configurés par Ansible"]
        app["app<br/>Caddy HTTPS, API, sonde"]
        pgs[("base<br/>PostgreSQL")]
        app --> pgs
    end

    subgraph cluster["Cluster k3d"]
        argo["Argo CD"]
        subgraph recette["vigie-recette"]
            r["API, CronJob sonde, PostgreSQL"]
        end
        subgraph production["vigie-production"]
            p["API x2, CronJob sonde, PostgreSQL"]
        end
        obs["Prometheus, Grafana, Loki, Alertmanager"]
        argo --> recette
        argo --> production
        obs -.->|"surveille"| production
    end

    git["Dépôt Git<br/>valeurs Helm par environnement"] --> argo
    ghcr --> app
    ghcr --> recette
    ghcr --> production
    production -->|"alertes sur les sites"| discord["Discord"]
    obs -->|"alertes sur la plateforme"| discord
```

## Ici et en entreprise

Le projet tourne en local, pour 0 € ([décision 0005](decisions/0005-tout-en-local-sans-frais.md)). Les gestes sont ceux de l'entreprise, seule la cible change. Ce tableau sera complété à chaque étape.

| Ici | En entreprise |
|---|---|
| Docker Compose sur le poste | Docker Compose sur un serveur, ou un orchestrateur |
| GitHub Actions et ghcr.io | Pareil, ou GitLab CI et un registre interne |
| Base PostgreSQL dans un conteneur, avec un volume | Base gérée par le fournisseur cloud, ou par un opérateur Kubernetes |
| Conteneurs système Incus (étape 9) | Machines virtuelles d'un cloud |
| État Terraform local (étape 9) | État dans un stockage distant, avec verrou |
| Cluster k3d (étape 11) | Kubernetes géré (EKS, GKE, AKS...) |
