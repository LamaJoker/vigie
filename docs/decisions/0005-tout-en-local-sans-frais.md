# 0005. Tout en local, pour 0 € : Incus et k3d plutôt qu'un cloud

- **Statut :** acceptée
- **Date :** 2026-11-10

## Contexte

Le budget du projet est de 0 €, sans carte bancaire. Les étapes 9 à 13 demandent pourtant des serveurs à créer par du code (Terraform), à configurer (Ansible), un cluster Kubernetes et une pile de supervision. Le poste de travail est un PC Windows avec WSL2 (16 processeurs, 15 Go de mémoire visibles par Linux).

## Décision

- **Serveurs** : des conteneurs système **Incus** dans WSL. Ils démarrent systemd, acceptent SSH et font tourner Docker, comme de petites machines. Terraform les crée par son fournisseur Incus, Ansible les configure. Un essai de faisabilité (lot 9.1) vient avant tout le reste, avec un plan B : le fournisseur Terraform `docker`.
- **Kubernetes** : un cluster **k3d** (k3s dans Docker), avec 1 serveur et 2 agents.
- **Images** : GitHub Container Registry, gratuit pour un dépôt public.
- **Chaque outil installé est épinglé** (version et somme de contrôle), et rien ne tourne en permanence sur le poste sans accord.
- Chaque compte rendu compare « ici » et « dans un cloud » : Incus face aux machines virtuelles, état Terraform local face à un stockage distant, k3d face à un Kubernetes géré.

## Conséquences

- Aucun coût, et tout se recrée à l'identique sur n'importe quel PC Linux.
- Les gestes appris sont ceux de l'entreprise (Terraform, Ansible, Helm, Argo CD), seule la cible change.
- Tout tient sur une machine : si le PC s'éteint, plus rien ne tourne ni n'alerte. C'est une limite assumée et documentée.
- Il faut surveiller la mémoire quand Kubernetes, Argo CD et la supervision tournent ensemble.

## Solutions écartées

- **Offres gratuites des clouds** : elles demandent une carte bancaire, et une erreur de configuration peut coûter cher.
- **Machines virtuelles VirtualBox avec Vagrant** : plus lourdes, plus lentes, et en conflit avec l'hyperviseur de WSL2 sur ce poste.
- **Docker Desktop** : inutile, Docker Engine tourne directement dans WSL.
