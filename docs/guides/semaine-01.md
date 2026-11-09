# Semaine 1 : poste de travail et Git

**Objectif :** à la fin de la semaine, tu travailles à l'aise dans un terminal Linux, tu comprends les commandes Git de base et tu sais publier ton travail sur GitHub.

**Temps prévu :** environ 20 heures.

| Étape | Durée indicative |
|---|---|
| 1. Prendre en main l'installation | 1 h |
| 2. Sécuriser ton compte Linux | 30 min |
| 3. Apprendre les bases du terminal | 10 h |
| 4. Apprendre Git | 5 h |
| 5. Clé SSH et compte GitHub | 2 h |
| 6. Écrire le journal de la semaine | 1 h |

Note tes heures au fur et à mesure dans ton journal ([docs/journal/semaine-01.md](../journal/semaine-01.md)).

---

## 1. Ce qui est déjà installé

Le 9 novembre, l'installation a été faite pour toi :

- **WSL2** (le Linux intégré à Windows) avec **Ubuntu 26.04 LTS** ;
- ton compte Linux **`valen`**, pour l'instant **sans mot de passe**, avec `sudo` qui ne demande pas de mot de passe ;
- les mises à jour d'Ubuntu ;
- l'extension **WSL** de VS Code ;
- **Git**, configuré avec ton nom et ton adresse e-mail, et relié à ton compte GitHub ;
- le projet, copié dans `~/vigie`, avec un premier commit.

### Ouvrir Ubuntu

- Dans le **Terminal** Windows, clique sur la flèche **˅** à côté du **+**, puis choisis **Ubuntu** ;
- ou tape `wsl` dans n'importe quel terminal Windows.

### Ouvrir le projet dans VS Code

```bash
cd ~/vigie
code .
```

En bas à gauche de VS Code, tu dois voir `WSL: Ubuntu`. À partir de maintenant, ouvre tes projets de cette façon, depuis Ubuntu.

### Comprendre où sont les fichiers

- Ton dossier personnel Linux : `/home/valen`, raccourci `~`.
- Le disque `C:` de Windows, vu depuis Linux : `/mnt/c`. **Attention :** une suppression dans `/mnt/c` efface de vrais fichiers Windows.
- Depuis l'Explorateur Windows, les fichiers Linux sont accessibles dans **Linux → Ubuntu**, en bas du panneau de gauche.

## 2. Sécuriser ton compte Linux (30 min)

Un compte sans mot de passe avec un `sudo` qui ne demande rien, c'est pratique pour démarrer, mais ce n'est pas acceptable sur un vrai serveur. Corrige-le :

1. Donne un mot de passe à ton compte :

   ```bash
   sudo passwd valen
   ```

   Rien ne s'affiche pendant la frappe, c'est normal.

2. Vérifie que ça marche : `su - valen` doit te demander ce mot de passe (tape `exit` pour revenir).
3. **Seulement après**, supprime la règle qui dispense `sudo` de mot de passe :

   ```bash
   sudo rm /etc/sudoers.d/90-valen
   ```

4. Teste avec `sudo -k`, puis `sudo whoami` : `sudo` doit maintenant te demander ton mot de passe.

> **Filet de sécurité :** si tu perds ton mot de passe, ouvre PowerShell et tape `wsl -u root`. Tu arrives dans Ubuntu en administrateur et tu peux relancer `passwd valen`.

## 3. Les bases du terminal (10 h)

Suis un cours d'introduction à la ligne de commande Linux (par exemple le cours gratuit d'OpenClassrooms sur Linux), puis fais les défis ci-dessous **dans ton terminal Ubuntu**. Note dans ton journal les commandes que tu découvres.

### Défi 1 : se repérer

- Affiche le dossier où tu te trouves (`pwd`), puis son contenu (`ls`, puis `ls -la`). Que sont les fichiers qui commencent par un point ?
- Crée cette arborescence dans ton dossier personnel avec `mkdir` et `cd` :

  ```
  ~/labo/
  ├── notes/
  └── scripts/
  ```

### Défi 2 : manipuler des fichiers

- Crée `~/labo/notes/commandes.txt` avec l'éditeur `nano`. Écris-y trois commandes apprises, enregistre (Ctrl+O, puis Entrée) et quitte (Ctrl+X).
- Copie le fichier (`cp`), renomme la copie (`mv`), puis supprime-la (`rm`).
- Affiche le fichier avec `cat`, puis avec `less` (touche `q` pour quitter).

### Défi 3 : les droits

- Lance `ls -l` et lis les colonnes `rwx` : qui a le droit de lire, d'écrire, d'exécuter ?
- Crée `~/labo/scripts/bonjour.sh` avec ce contenu :

  ```bash
  #!/bin/bash
  echo "Bonjour $USER, nous sommes le $(date)"
  ```

- Lance-le avec `./bonjour.sh` depuis le dossier `scripts` : ça échoue. Pourquoi ? Corrige avec `chmod +x bonjour.sh` et relance.
- Lance `ls -l /mnt/c/Users` : pourquoi les fichiers Windows ont-ils tous les droits vus depuis Linux ?

### Défi 4 : installer des logiciels

- Installe deux outils : `sudo apt install tree htop`
- Affiche ton arborescence `~/labo` avec `tree`.
- Que fait `sudo` ? Où apt va-t-il chercher les logiciels ? (Indice : `/etc/apt/sources.list.d/`.)

### Défi 5 : chercher et enchaîner

- Cherche un mot dans `commandes.txt` avec `grep`.
- Trouve tous les fichiers `.sh` sous `~/labo` avec `find`.
- Le tube `|` : que fait `ls /etc | wc -l` ?
- Les redirections : quelle différence entre `>` et `>>` ? Essaie les deux sur un fichier de test.

### Défi 6 : les processus

- Lance `htop`, repère le processus qui utilise le plus de mémoire, puis quitte avec `q`.
- Que montre `ps aux | grep bash` ?

### Défi final : un avant-goût de Vigie

Interroge un site comme le fera Vigie :

```bash
curl -I https://www.wikipedia.org
```

Repère le code HTTP dans la première ligne (`200` veut dire que tout va bien). Cette variante n'affiche que le code et le temps de réponse :

```bash
curl -s -o /dev/null -w "%{http_code} %{time_total}s\n" https://www.wikipedia.org
```

**Ton défi :** écris une seule ligne de commande qui **ajoute** dans `~/labo/notes/sondes.log` la date, puis le code HTTP du site. Lance-la trois fois et affiche le fichier. Indices : `$(...)` et `>>`.

Tu viens d'écrire la toute première version de Vigie.

## 4. Git (5 h)

Git garde l'historique de chaque modification. En entreprise, tout passe par Git : le code, mais aussi l'infrastructure et la configuration.

1. Fais les deux premières séries de niveaux de [Learn Git Branching](https://learngitbranching.js.org/?locale=fr_FR) (disponible en français).
2. Regarde la configuration qui a été faite pour toi : `git config --global --list`. Que veut dire chaque ligne ?
3. Explore ton dépôt :

   ```bash
   cd ~/vigie
   git status
   git log
   git remote -v
   ```

4. Voici les commandes qui ont servi à créer le dépôt et à le publier. Pour chacune, note dans ton journal ce qu'elle fait :

   ```bash
   git init
   git add .
   git commit -m "docs: point de départ du projet Vigie"
   git remote add origin https://github.com/LamaJoker/vigie.git
   git push -u origin main
   ```

5. Apprends aussi : `git diff`, `git pull`, `git branch`, `git switch`.

## 5. Clé SSH et compte GitHub (2 h)

### 5.1 Ajouter ton adresse e-mail sur GitHub

Tes commits sont signés avec `valentin.besancon.acdf@gmail.com`. Pour qu'ils apparaissent sur ton profil (le calendrier vert que regardent les recruteurs), ajoute cette adresse dans GitHub : **Settings → Emails → Add email address**, puis valide le lien reçu par e-mail.

### 5.2 Créer une clé SSH

Pour l'instant, Git passe par le GitHub CLI de Windows pour s'identifier. Les DevOps utilisent surtout des **clés SSH**, pour GitHub comme pour se connecter aux serveurs. Tu t'en serviras à la semaine 10 avec Ansible. Crée la tienne dès maintenant :

```bash
ssh-keygen -t ed25519 -C "vigie-wsl"
```

Garde l'emplacement proposé (Entrée) et choisis une phrase de passe. Affiche ensuite la partie **publique** :

```bash
cat ~/.ssh/id_ed25519.pub
```

Colle-la dans GitHub : **Settings → SSH and GPG keys → New SSH key**. Le fichier sans `.pub` est ta clé privée : il ne doit jamais quitter ta machine.

Teste la connexion :

```bash
ssh -T git@github.com
```

GitHub doit te répondre en t'appelant par ton pseudo. Bonus : bascule ton dépôt en SSH avec `git remote set-url origin git@github.com:LamaJoker/vigie.git`, puis vérifie avec `git remote -v`.

### 5.3 Bonus : le tableau de suivi

Dans ton dépôt sur GitHub, onglet **Projects**, crée un projet au format **Board**. Ajoute un ticket (issue) par semaine de la feuille de route et range-les dans les colonnes « À faire », « En cours » et « Terminé ». En entreprise, le travail s'organise de cette façon.

## 6. Le journal

Remplis [docs/journal/semaine-01.md](../journal/semaine-01.md), coche les cases terminées dans [ROADMAP.md](../../ROADMAP.md), puis envoie le tout **toi-même** :

```bash
cd ~/vigie
git add .
git commit -m "docs: journal de la semaine 1"
git push
```

## Pour valider la semaine

Tu dois pouvoir expliquer sans tes notes :

- la différence entre Windows, Linux et WSL ;
- ce que font `sudo`, `chmod +x`, `|` et `>>` ;
- pourquoi un `sudo` sans mot de passe est dangereux sur un serveur ;
- la différence entre `git add`, `git commit` et `git push` ;
- pourquoi une clé SSH a une partie publique et une partie privée.

Quand tu as fini, montre-moi ton dépôt : on relit ensemble et on attaque la semaine 2.
