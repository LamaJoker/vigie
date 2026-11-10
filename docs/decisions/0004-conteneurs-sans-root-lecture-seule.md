# 0004. Conteneurs sans root, en lecture seule, sans capacités Linux

- **Statut :** acceptée
- **Date :** 2026-11-09 (écrite le 2026-11-10)

## Contexte

Un conteneur qui tourne en root et dont le système de fichiers est modifiable offre beaucoup de prise à un attaquant qui exploiterait une faille de l'application. Vigie fait des requêtes vers des sites extérieurs et sert une page web : ce sont deux points d'entrée possibles.

## Décision

- L'image tourne avec un utilisateur dédié, **désigné par un numéro fixe (UID 10001)**. Kubernetes a besoin d'un numéro pour vérifier qu'un conteneur ne tourne pas en root.
- Dans la pile Compose : système de fichiers **en lecture seule**, seuls deux dossiers de travail en mémoire sont inscriptibles ; **aucune capacité Linux** (`cap_drop: ALL`) ; interdiction de gagner des droits (`no-new-privileges`).
- L'image est construite en deux étapes : ni outils de construction, ni tests, ni secrets dans l'image finale.
- Un essai de bout en bout vérifie ces propriétés à chaque passage de l'intégration continue.

## Conséquences

- Une faille de l'application donnerait très peu de pouvoir à un attaquant.
- Le durcissement casse parfois des choses qui marchaient : à l'étape 6, la sonde ne pouvait plus écrire son fichier verrou. Seul l'essai dans les vraies conditions l'a révélé.
- Ces réglages se transposent directement au niveau de sécurité `restricted` de Kubernetes (étape 11).

## Solutions écartées

- **Image par défaut, en root** : plus simple, mais refusée par les politiques de sécurité courantes, et mauvaise habitude.
- **Image « distroless »** : encore plus réduite, mais sans shell, ce qui complique l'apprentissage et le dépannage. À reconsidérer plus tard.
