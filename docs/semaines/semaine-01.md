# Semaine 1 : poste de travail et Git

**Période :** du 9 au 15 novembre 2026
**Statut :** en cours

## Objectif

Disposer d'un poste de travail DevOps complet sous Windows : un vrai Linux, un éditeur relié à ce Linux, Git, et un dépôt public où suivre le projet.

## Ce qui a été fait

### Le poste de travail

- **WSL2 et Ubuntu 26.04 LTS.** La grande majorité des serveurs tournent sous Linux. WSL2 fait tourner un vrai noyau Linux dans une machine virtuelle légère gérée par Windows : pas de double démarrage, pas de partition, et les fichiers Linux restent dans un disque virtuel séparé.
- **Compte Linux `valen`**, puis mise à jour complète du système (`apt update` puis `apt upgrade`).
- **VS Code relié à Ubuntu** avec l'extension WSL : l'éditeur s'affiche sous Windows, mais les fichiers, le terminal et les outils sont ceux de Linux. Le projet est rangé côté Linux (`~/vigie`), où les outils, et plus tard Docker, sont bien plus rapides.

### Git et GitHub

- **Git configuré** : nom, adresse e-mail, branche par défaut `main`.
- **Accès à GitHub sans mot de passe stocké dans Ubuntu.** Git demande les identifiants au GitHub CLI de Windows, déjà connecté (mécanisme du *credential helper*).
- **Dépôt public créé**, premier commit publié.
- **`.gitattributes`** impose les fins de ligne Unix (LF). Un script Bash enregistré avec des fins de ligne Windows (CRLF) refuse de s'exécuter : c'est une erreur classique quand on travaille entre Windows et Linux.
- **`.gitignore`** exclut déjà les secrets (`.env`, clés) et les fichiers générés, en prévision des semaines suivantes.

### Organisation

- Les commits suivent la convention **Conventional Commits** (`feat:`, `fix:`, `docs:`…), ce qui rend l'historique lisible d'un coup d'œil.
- Chaque changement passe par une **branche** et une **pull request**, relue et validée avant d'arriver sur `main`. Le modèle `.github/pull_request_template.md` oblige à décrire le changement, sa raison et la façon de le vérifier.

## Incident : installation bloquée

**Ce qui s'est passé.** La première commande d'installation a activé WSL mais n'a pas téléchargé Ubuntu. Une fois Ubuntu ajouté, l'assistant de création du compte est resté en attente dans une session que personne ne voyait. Tant qu'il attendait, toutes les commandes WSL bloquaient, y compris l'arrêt de WSL.

**Résolution.** Redémarrage du PC, puis création du compte en ligne de commande, en administrateur, sans passer par l'assistant interactif.

**Leçon.** Une étape interactive (saisir un nom, un mot de passe) bloque une automatisation. En DevOps, on préfère les installations non interactives, qu'on peut rejouer à l'identique.

## Points de sécurité ouverts

- Le compte `valen` n'a pas encore de mot de passe, et `sudo` n'en demande pas. C'est tolérable quelques jours sur un poste personnel, jamais sur un serveur. À faire : définir un mot de passe (`sudo passwd valen`), puis supprimer la règle `/etc/sudoers.d/90-valen`.
- Pas encore de clé SSH : l'accès à GitHub passe par le GitHub CLI.

## Comment vérifier

- Ouvrir https://github.com/LamaJoker/vigie : le README s'affiche.
- Dans Ubuntu : `cd ~/vigie`, puis `git log --oneline` (historique) et `git remote -v` (lien avec GitHub).
- Dans PowerShell : `wsl -l -v` affiche Ubuntu en version 2.

## Vocabulaire de la semaine

| Terme | Sens |
|---|---|
| WSL2 | Sous-système Windows pour Linux : un vrai Linux dans une machine virtuelle légère |
| Distribution | Une version de Linux avec ses outils (Ubuntu, Debian…) |
| `sudo` | Lancer une commande avec les droits d'administrateur (root) |
| Dépôt | Dossier suivi par Git, avec tout son historique |
| Commit | Instantané enregistré des fichiers, accompagné d'un message |
| Branche | Ligne de travail parallèle ; `main` est la branche principale |
| Pull request | Demande de fusion d'une branche dans `main`, avec relecture |
| Credential helper | Programme qui fournit à Git les identifiants de connexion |

## Temps de supervision

| Jour | Activité | Durée |
|---|---|---|
| Lun. 9/11 | Choix du projet, suivi de l'installation, relecture | |
| | | |

**Total :** h
