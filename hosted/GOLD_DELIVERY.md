# Adaptation XAUUSD — 25 octobre 2026

Le pilote hébergé utilise XAUUSD (or/USD), démo USD uniquement. Le connecteur
historique reste EURUSD. La stratégie CHoCH/retest/rejet M3 reste inchangée ;
aucun passage en EA MQL5, aucune rentabilité ou exécution courtier validée.

- Le moteur vérifie currency_base=XAU et currency_profit=USD, accepte un nom
  courtier avec suffixe, refuse les autres actifs. Saisir le nom exact dans le site.
- Calcul de perte et marge fourni par MT5, lots arrondis vers le bas selon les
  contraintes courtier, protections arrondies au tick. Risque max 1 %, perte
  quotidienne max 3 %, une position/ordre sur le compte, démo uniquement conservés.
- Provision glissement 0,10 USD/once + 10 points et commission estimée
  3,50 USD/lot/sens, à vérifier sur compte démo ; aucune garantie contre les gaps.
- Le tableau de bord affiche le symbole et la précision courtier. Le laboratoire
  Forex refuse un historique MT5 or pour éviter des calculs de contrats incorrects.
- Refus de démarrage explicites (prix périmé, autorisations, symbole). Les erreurs
  réseau signalent un état incertain ; aucune relance automatique d'ordre.

## Validation exécutée

46 tests Python connector (dont 7 tests or), 16 tests Python hosted, test Node du
tableau de bord (or et précision inclus), test proxy hosted, parité backtest
Python/JS Forex (16 transactions simulées), contrôles syntaxe JS et git diff --check.
Tous passent. Les API MT5 sont simulées. Aucun ordre transmis à un courtier.

## Mise à jour sur le portable

Arrêter l'hôte avec Ctrl+C, garder le tunnel ouvert. Depuis la racine du projet,
exécuter hosted/UPDATE_XAUUSD.ps1 téléchargé depuis cette branche. Le script
stage et vérifie le Python puis sauvegarde et remplace uniquement sept fichiers de
code. Il ne touche pas pool.json, service-key.txt, terminaux, affectations ou risque.
Relancer l'hôte avec la clé existante et PUBLIC_URL. Se reconnecter au site.
Le bot reste arrêté après redémarrage. Ne pas copier les dossiers data d'une archive.

Le script PowerShell n'a pas été exécuté sur Windows dans cet environnement.
Restent à valider sur le PC : symbole exact XAUUSD et suffixe, cotations ouvertes,
spécifications réelles, Démarrer/Arrêter et séparation de deux comptes démo.
Les anciennes limites d'hébergement et l'avertissement Windows restent applicables.
