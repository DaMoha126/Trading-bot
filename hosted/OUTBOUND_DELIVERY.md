# Liaison PC → Render, sans tunnel

Cette livraison remplace le proxy entrant Ngrok/Cloudflare par un relais HTTP
sortant authentifié. Aucun changement de stratégie, de risque, de terminal,
de compte ni de mot de passe MT5. La version expérimentale M1 reste indépendante.

## Configuration

Render garde le lancement `node hosted/proxy.mjs`, `MT5_HOST_KEY` et `PUBLIC_URL`
existants. `MT5_HOST_URL` n'est plus utilisé. Ne pas supprimer/modifier la clé.
Le relais nécessite une seule instance : sa file et ses requêtes en cours sont
volontairement éphémères. Pas de facturation ni de ressources ajoutées.

Le PC utilise la même clé de service `MT5_HOST_KEY`, saisie masquée si elle n'est
pas déjà dans son environnement. Cette clé est distincte du mot de passe MT5.
Le lancement ne l'enregistre pas sur disque et ne l'affiche pas.
Le service local reste exclusivement sur 127.0.0.1:8770.

## Installation Windows

Dans PowerShell, depuis le dossier contenant `hosted/pool.json` :

```powershell
Invoke-WebRequest -UseBasicParsing 'https://raw.githubusercontent.com/DaMoha126/Trading-bot/feature/hosted-mt5-pilot/hosted/INSTALLER_SANS_TUNNEL.ps1' -OutFile INSTALLER_SANS_TUNNEL.ps1
powershell -ExecutionPolicy Bypass -File .\INSTALLER_SANS_TUNNEL.ps1
```

L'installation ajoute uniquement les fichiers de liaison ; elle ne remplace pas
le moteur ni les réglages existants. Arrêter l'ancien service avec Ctrl+C avant
le nouveau lancement. Cela peut interrompre la gestion active d'une position :
contrôler les positions et leurs protections dans MT5 avant l'arrêt.

```powershell
powershell -ExecutionPolicy Bypass -File .\hosted\LANCER_SANS_TUNNEL.ps1
```

Garder MT5 et cette fenêtre ouverts. Plus besoin de Ngrok, Cloudflare, domaine
personnel ou règle de redirection de port. Une connexion sortante HTTPS au site
Render et l'accès du terminal au courtier restent nécessaires.

## Comportement et limites

- Le navigateur utilise toujours la même URL Render et les sessions du service local.
- PC hors ligne : page explicite « Moteur du PC déconnecté » et réponses API 503.
- La reconnexion du transport est automatique ; elle n'active aucun bot.
- Un nouveau lancement du service MT5 reste à l'arrêt comme avant.
- Pas de répétition d'une requête déjà distribuée, même si la réponse se perd.
- Après une réponse incertaine, vérifier MT5 avant de soumettre une nouvelle commande.
- Les files en cours expirent après 25 secondes et disparaissent au redémarrage Render.
- Une coupure n'arrête pas automatiquement un moteur déjà autonome sur le PC.
  Le mode supervisé conserve sa règle de pause existante quand le site n'est plus actif.
- Fermer le lanceur arrête le service ; ne pas supposer que cela clôture les positions.
  Les protections SL/TP sont maintenues par le courtier quand elles ont été acceptées.
- L'offre Render existante conserve ses limitations ; aucune disponibilité continue garantie.
- Le lanceur Windows et la liaison réelle au PC restent à vérifier sur la machine utilisateur.

## Vérifications réellement exécutées

- 7 tests Node du relais : authentification, origine, bornage de file, expiration,
  absence de redistribution, cookies, refus des redirections externes.
- 7 tests Python : routage local borné, origine, cookies, corps, déduplication,
  absence de répétition après erreur, réponse explicite en cas d'incertitude.
- 1 test d'intégration avec serveurs HTTP locaux Node et Python : connexion,
  cookie HttpOnly et commande stop simulée, une seule transmission.
- Compilation syntaxique des deux programmes Python.

Aucun ordre MT5 envoyé ; aucune rentabilité ou exécution courtier validée par ces tests.
