# Réglages utilisateur du scalper démo M1

Un onglet Réglages est ajouté à la navigation du tableau de bord. Le formulaire
modifie les paramètres utilisés par le moteur, pas uniquement des valeurs affichées.

## Paramètres

- Risque total de la série : 0,01 à 1 % ; limite quotidienne : jusqu'à 3 %.
- 1 à 3 positions par signal ; risque partagé entre elles.
- Attente après fermeture : 0 à 3 600 secondes.
- Pivots : 1 à 10 bougies clôturées de chaque côté.
- Dépassement du niveau : 0,01 à 10 unités de prix XAUUSD (USD/once).
- Distance du stop : 0,05 à 100 unités de prix ; spread maximal : 0,01 à 10.
- Break-even activable et déclenchement entre 10 et 90 % du chemin vers le TP.
- Filtre horaire activable, deux plages en heures UTC, passages de minuit gérés.

L'objectif reste la prochaine zone de liquidité et le CHoCH reste une sortie.
Les comptes réels sont refusés, les contrôles de prix et de broker sont conservés.
Le risque prévu peut être dépassé par les conditions d'exécution.

## Enregistrement

L'action authentifiée `settings` n'est autorisée qu'à l'arrêt. Les valeurs sont
validées côté serveur puis enregistrées pour le compte login@serveur dans son
état de risque existant. Un nouveau démarrage reconstruit les pivots avec ces valeurs.
Les réglages d'un compte ne chargent pas ceux d'un autre. Aucun mot de passe ou
clé n'est enregistré par le formulaire. Une limite quotidienne déjà déclenchée
n'est pas effacée en changeant les réglages.

Les modifications non enregistrées restent des brouillons. Valeurs par défaut
prépare le formulaire mais ne l'enregistre pas. Aucun enregistrement ne démarre
un bot ni ne modifie les SL/TP des positions existantes.

## Installation

Depuis le projet sur le PC : arrêter le service, garder MT5 ouvert, puis lancer
`hosted/UPDATE_SETTINGS.ps1` et relancer `hosted/LANCER_SANS_TUNNEL.ps1`.
Le script conserve la liaison sortante, les clés, le registre des comptes et les
terminaux. Il sauvegarde les fichiers qu'il remplace. Le service doit être arrêté
pour éviter une mise à jour pendant son exécution. Une gestion active de positions
est interrompue pendant cet arrêt : vérifier MT5 et ses protections auparavant.

Le tableau de bord est servi par le PC via le relais Render ; aucun nouveau
déploiement Render n'est nécessaire pour ces paramètres.

## Validation réalisée

- 49 tests du connecteur : paramètres invalides, comptes distincts, persistance,
  quantité de positions, budget de risque, break-even, heures UTC et contrôles existants.
- 16 tests du service hébergé dont l'acceptation authentifiée de l'action settings.
- Test DOM de l'interface : navigation, brouillon conservé, requête d'enregistrement,
  rechargement, changement de compte, défauts sans enregistrement et blocage en marche.
- Vérification syntaxique de control.js et des modules Python.

Pour le test DOM, installer jsdom@30.1.3 comme dépendance de développement, puis
exécuter `node test-settings-dom.cjs`. Les tests utilisent des comptes et ordres simulés.
Le test visuel Chromium n'a pas pu être exécuté : le téléchargement du navigateur
est bloqué dans l'environnement de développement. Le contrôle visuel sur téléphone
et l'installation Windows restent à confirmer. Aucun ordre MT5 n'a été envoyé.
