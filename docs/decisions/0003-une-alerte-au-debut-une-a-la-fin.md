# 0003. Une alerte au début d'un incident, une à la fin, rien entre les deux

- **Statut :** acceptée
- **Date :** 2026-11-09 (écrite le 2026-11-10)

## Contexte

La sonde passe toutes les 5 minutes. Alerter à chaque passage en échec noierait le destinataire sous les messages, et une alerte répétée finit par être ignorée. À l'inverse, une alerte perdue (Discord injoignable) ne doit pas rester perdue.

## Décision

- Les pannes sont regroupées en **incidents**. Un incident s'ouvre après N échecs consécutifs (2 par défaut, réglable) et se ferme au premier succès.
- **Deux alertes par incident** : « panne » à l'ouverture, « rétabli » à la fermeture, avec la durée.
- **Un seul incident ouvert par site**, garanti par un index unique partiel de la base, pas seulement par le code.
- **Livraison « au moins une fois »** : chaque incident note si ses alertes sont parties. Une alerte non confirmée est renvoyée au passage suivant.
- L'adresse du webhook Discord est un **secret** : elle vient d'une variable d'environnement et n'est jamais affichée.

## Conséquences

- Un raté isolé ne réveille personne, et une panne réelle est signalée environ 10 minutes après son début, avec le réglage par défaut.
- La durée affichée part du premier échec : elle est juste.
- Les alertes ont besoin de la base : sans elle, impossible de savoir si une panne est déjà signalée.

## Solutions écartées

- **Une alerte à chaque échec** : spam assuré.
- **Un état tenu en mémoire par la sonde** : perdu à chaque redémarrage du conteneur, d'où des alertes en double ou manquées.
- **Confier tout de suite les alertes à un outil dédié (Alertmanager)** : prévu pour superviser la plateforme elle-même à l'étape 13, pas pour remplacer la logique métier des sites.
