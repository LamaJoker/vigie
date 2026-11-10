# 0001. Le projet est réalisé par un assistant IA, supervisé

- **Statut :** acceptée
- **Date :** 2026-11-09 (écrite le 2026-11-10)

## Contexte

Vigie est un projet de formation au métier de DevOps, publié sur GitHub pour être montré. Son porteur a choisi de ne pas écrire le code lui-même : il fait réaliser le travail par un assistant IA de programmation (Claude, d'Anthropic) et en assure la supervision.

## Décision

- L'assistant réalise le travail et le propose en pull requests, petites et relisibles, avec leurs explications.
- Le superviseur fixe les objectifs, valide les choix, relit, et décide seul de fusionner. Il décide aussi de tout réglage du dépôt ou de son compte.
- Le dépôt le dit clairement : section « Méthode de travail » du README, et mention `Co-Authored-By` dans chaque commit écrit par l'assistant.
- Chaque étape a un compte rendu qui explique le travail pour que le superviseur puisse le comprendre et le présenter. À partir du lot 0, il se termine par un « parcours du superviseur » : des commandes à lancer, une panne à provoquer, des questions avec leurs réponses.
- Rien n'est annoncé comme fonctionnel sans avoir été exécuté. Les comptes rendus distinguent ce qui est vérifié de ce qui ne l'est pas, et ils racontent les incidents rencontrés.

## Conséquences

- Le projet avance vite et couvre largement les pratiques DevOps.
- La transparence sur la méthode est une force : savoir encadrer un assistant IA, relire son travail et exiger des preuves est une compétence recherchée.
- Le risque, c'est un dépôt que son porteur ne sait pas expliquer. Le parcours du superviseur et le futur guide d'entretien (lot 14.2) sont là pour ça.

## Solutions écartées

- **Présenter le travail comme personnel** : malhonnête, et intenable en entretien technique.
- **Faire écrire tout le code au superviseur, avec l'assistant comme simple guide** : c'était la proposition de départ, que le porteur du projet a refusée.
