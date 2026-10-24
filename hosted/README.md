# Connexion directe MT5 — pilote sur le portable de Ben

## État réel

Code de pilote, distinct du serveur v4 actuel. Les visiteurs saisissent identifiant MT5,
serveur et mot de passe de trading sur `/login`. Le site vérifie le compte auprès du
terminal Windows préparé par Ben. Une session opaque donne accès uniquement au moteur
de ce compte. Aucun ordre au login. Comptes démo USD et stratégie EUR/USD uniquement.

Ce mode n'est pas activé automatiquement sur Render. Le portable doit d'abord être
configuré et testé. Aucun test Windows, courtier ou passage d'ordre réel n'est revendiqué.

## Architecture du pilote

- Render lance `node hosted/proxy.mjs` : relais HTTPS vers une seule adresse autorisée.
- Le portable lance `hosted/host.py`, qui écoute seulement sur `127.0.0.1:8770`.
- Cloudflare Tunnel transporte les requêtes. Sa clé de service privée est connue seulement
  de Render et du portable ; les visiteurs ne la saisissent pas.
- Un processus Python et un terminal MT5 portable dédiés par compte configuré. Fichiers
  de risque et journal séparés par empreinte de l'identité du compte.
- Le portable n'est pas une isolation système complète : l'administrateur et un processus
  compromis avec ses droits peuvent atteindre les terminaux. Ce pilote est destiné à un
  petit groupe de confiance ; ne pas le présenter comme un service public prêt à grande échelle.

## Préparer le portable Windows (administrateur Ben)

1. Garder le portable alimenté, connecté et sans veille ; capot fermé uniquement si les
   options Windows l'autorisent et si le refroidissement est suffisant.
2. Installer Python 3.10+ 64 bits, Node n'est pas nécessaire sur le portable.
3. Récupérer ce dépôt et installer la dépendance :

   ```powershell
   py -3 -m venv .venv
   .\.venv\Scripts\python.exe -m pip install MetaTrader5
   ```

4. Préparer une installation MT5 **distincte par compte** avec son propre dossier, par
   exemple `C:/TradingBot/Terminals/client-01/terminal64.exe`. Lancer cette installation
   en mode `/portable`, depuis un dossier accessible en écriture. Ne pas pointer plusieurs
   comptes vers le même exécutable. Prévoir le bon terminal du courtier et tester le serveur.
   Vérifier que Fichier → Ouvrir le dossier des données ouvre le dossier dédié en mode
   portable ; l'hôte refuse une autre localisation. Ne charger aucun EA sur ses graphiques,
   afin que seul notre moteur puisse demander des ordres après Démarrer.
5. Dans chaque terminal, autoriser le trading algorithmique et décocher le blocage de
   l'API Python externe. Les mots de passe investisseur ne permettent pas ce pilote.
6. Copier `hosted/accounts.example.json` vers `hosted/accounts.json`. Remplacer login,
   serveur et chemin par ceux du compte démo autorisé. Ne pas y inscrire de mot de passe.
   Chaque nouveau compte doit être préparé par Ben ; l'inscription libre n'est pas implémentée.
7. Générer une clé de service aléatoire de 32 octets minimum et la conserver dans les
   variables d'environnement des deux systèmes. Ne pas la commettre ou l'envoyer dans le chat.
   Les paramètres requis dans la session PowerShell sont `MT5_HOST_KEY` et `PUBLIC_URL`
   (`https://ben-bot-mt5.onrender.com`). Puis lancer :

   ```powershell
   .\.venv\Scripts\python.exe hosted\host.py
   ```

8. Dans une autre fenêtre, lancer un tunnel vers l'hôte (cloudflared doit être installé) :

   ```powershell
   cloudflared tunnel --url http://127.0.0.1:8770 --no-autoupdate
   ```

   Les appels directs au tunnel sans clé de service sont refusés. Un tunnel temporaire
   change d'URL au relancement ; c'est Ben qui met à jour Render, pas les visiteurs.

## Basculer Render après vérification du portable

Conserver la configuration v4 pour revenir au mode précédent si nécessaire.
Configurer `MT5_HOST_URL` avec l'origine HTTPS du tunnel, `MT5_HOST_KEY` avec la même clé
que sur le portable, et `PUBLIC_URL` avec l'origine du site sans slash final.
Pour ce service Docker, définir la commande de démarrage sur `node hosted/proxy.mjs`.
Ne pas modifier les secrets APP_PASSWORD/SESSION_SECRET de la v4 : ils restent utiles
pour le retour à l'ancien mode, mais ne servent pas au login MT5 hébergé.

La bascule remplace le login commun par le login MT5 pour tous les visiteurs. Ne pas la
faire avant la validation sur le portable. Les comptes non préparés sont refusés.

## Recette obligatoire en démo

- Sans session : dashboard et API inaccessibles ; aucun secret dans le navigateur.
- Identifiants incorrects, compte réel/concours, devise autre qu'USD : refus.
- Deux comptes préparés : leurs soldes, positions, journaux et commandes restent séparés.
- La connexion seule n'active pas le moteur. Vérifier les prix et le symbole exact avant
  une demande Démarrer. Le moteur conserve les limites et contrôles v4.
- Démarrer/Arrêter : uniquement les nouvelles entrées ; aucune liquidation automatique.
- En mode supervisé, fermeture du navigateur = pause ; en mode autonome explicitement
  choisi, fonctionnement possible sans téléphone. Toute interruption de l'hôte peut empêcher
  l'arrêt distant ; intervenir localement si nécessaire.
- Couper le tunnel : état inconnu et aucune affirmation mensongère d'arrêt.
- Redémarrer l'hôte : sessions perdues et moteurs à l'arrêt. Les fichiers de risque restent.

## Identifiants et limites

Le mot de passe est transmis via HTTPS et le relais de confiance de Ben à MT5. Il n'est
pas écrit par notre application dans une base, un journal, un cookie ou des arguments de
processus. MT5 possède son propre stockage local : ne pas promettre qu'aucun identifiant
n'existe sur le disque du terminal. Protéger les dossiers et le compte Windows de l'hôte.

Un vérificateur scrypt est gardé en mémoire pendant la vie du processus pour ouvrir de
nouvelles sessions du même compte sans perturber le terminal déjà actif. Un changement
de mot de passe nécessite un arrêt/recontrôle et redémarrage de l'hôte ; les sessions web
durent au maximum 12 h. Fermer la session web ne stoppe pas un moteur autonome.

Limites : 10 comptes configurables au plus, capacité réelle du portable non mesurée ;
pas de récupération de mot de passe MT5, inscription libre, service Windows, redémarrage
automatique, haute disponibilité, historique central ou déploiement public multi-client
validé. Ne pas réutiliser le même terminal pour du trading manuel ou un autre bot.

## Vérifications automatisées

```sh
python -m unittest discover -s hosted -p 'test_*.py' -v
node --check hosted/proxy.mjs
node hosted/test-proxy.mjs
```

Ces tests utilisent des acteurs et un module MT5 simulés. Ils ne vérifient pas une
installation réelle Windows ou l'accès au courtier.
