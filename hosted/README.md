# Connexion directe MT5 — attribution automatique sur le portable

## État réel

Pilote distinct de la v4 en ligne. Chaque visiteur saisit son identifiant MT5, le serveur
du courtier et le mot de passe de trading. Un compte démo USD valide reçoit automatiquement
une place disponible : aucune création manuelle de son compte dans un fichier.
Aucun ordre n'est lancé à la connexion. XAU/USD uniquement pour le pilote hébergé.
Le connecteur historique reste EUR/USD. Stratégie CHoCH/retest/rejet M3 inchangée ;
aucune rentabilité sur l’or validée. Le laboratoire Forex ne convient pas à l’or.
Lots calculés via order_calc_profit MT5, arrondis vers le bas au pas courtier.
SL/TP arrondis au tick, avec contrôle de la distance minimale du courtier.
Provision de glissement : 0,10 USD/once plus 10 points ; commission estimée
3,50 USD/lot/sens. Hypothèses à vérifier en démo, pas un tarif courtier.
Gaps, swap et frais réels peuvent dépasser le budget prévu.

Les tests utilisent MT5 simulé. Installation Windows, initialisation des copies MT5,
connexion au courtier et exécution en démo restent à vérifier avant la bascule du site.

## Préparation unique par Ben

Ben prépare la capacité du serveur, pas chaque utilisateur. Exemple : deux places pour
commencer. Les dossiers terminaux sont créés automatiquement à partir d'un modèle MT5.
Une place reste affectée au compte après déconnexion pour préserver son état de risque.
Quand toutes les places sont affectées, les nouveaux comptes sont refusés clairement.
Ce pilote ne réaffecte pas automatiquement les terminaux et ne réinitialise pas leur risque.

1. Sur le portable Windows, installer Python 3.10+ 64 bits, garder Internet et désactiver
   la veille sur secteur. Le site reste sur Render.
2. Récupérer ce dépôt puis préparer Python :

   ```powershell
   py -3 -m venv .venv
   .\.venv\Scripts\python.exe -m pip install MetaTrader5
   ```

3. Installer une copie MT5 modèle dans un dossier dédié, par exemple
   `C:/TradingBot/TemplateMT5`. Utiliser un terminal authentique du courtier.
   Vérifier une fois qu'il connaît les serveurs démo proposés.
4. Copier `hosted/pool.example.json` vers `hosted/pool.json`. Indiquer :
   - `template` : dossier contenant terminal64.exe ;
   - `capacity` : nombre de places, 2 au départ, maximum technique 10 non dimensionné ;
   - `servers` : noms exacts des serveurs démo pris en charge.
   Aucun numéro de compte ni mot de passe utilisateur dans cette configuration.
5. Créer les places :

   ```powershell
   .\.venv\Scripts\python.exe hosted\host.py --prepare-only
   ```

   Seuls terminal64.exe et, si présent, Config/servers.dat sont copiés. Ni comptes,
   profils, journaux, ni EA du modèle ne sont clonés. Cette initialisation minimale doit
   être validée sur le portable : ne pas prétendre à une installation Windows déjà testée.
6. À la préparation initiale de la capacité, ouvrir chaque copie créée en mode
   `/portable`, autoriser le trading algorithmique et l'API Python externe.
   Ne charger aucun EA sur ses graphiques. Vérifier que « Ouvrir le dossier des données »
   pointe sur son dossier dédié. Ces réglages concernent les places une fois, pas chaque
   nouvel utilisateur. Le programme refuse une instance qui utilise un autre dossier.
7. Configurer une clé de service aléatoire de 32 octets minimum dans `MT5_HOST_KEY` et
   `PUBLIC_URL=https://ben-bot-mt5.onrender.com` dans l'environnement de lancement.
   Garder la clé privée ; ne pas l'envoyer dans le chat ou la commettre. Lancer l'hôte :

   ```powershell
   .\.venv\Scripts\python.exe hosted\host.py
   ```

8. Dans une autre fenêtre, lancer le tunnel (cloudflared installé) :

   ```powershell
   cloudflared tunnel --url http://127.0.0.1:8770 --no-autoupdate
   ```

Un nouveau courtier/serveur peut demander une préparation de son support dans MT5.
L'acceptation automatique ne signifie pas que tous les courtiers et serveurs du monde
fonctionnent. Les comptes réels, concours et non-USD restent refusés.

## Fonctionnement

Render utilise `node hosted/proxy.mjs` comme commande de démarrage et les variables
`MT5_HOST_URL` (origine HTTPS du tunnel), `MT5_HOST_KEY` (même clé que le portable)
et `PUBLIC_URL` (origine du site sans slash final). Le relais n'accepte qu'une destination
trycloudflare.com configurée. Les appels directs au tunnel sans clé sont refusés.

L'hôte écoute sur 127.0.0.1:8770. Il réserve une instance seulement après validation MT5.
Chaque compte dispose de son processus Python, terminal, fichiers de risque et journal.
Les affectations sont sauvegardées atomiquement dans hosted/data/assignments.json.
Au redémarrage, elles sont relues ; les sessions web sont perdues et les moteurs repartent
à l'arrêt. Ne pas supprimer ce registre ni les fichiers de risque pour libérer des places.
L'ancienne configuration accounts.json reste compatible si aucun pool.json n'est présent.

Le tunnel temporaire peut changer : c'est Ben qui met à jour Render, jamais les visiteurs.
Ne pas basculer le site avant la recette Windows. La commande v4 `node server.mjs` et
ses secrets existants restent disponibles pour revenir au mode précédent.

## Identifiants et limites

Les mots de passe traversent HTTPS et le relais de confiance de Ben. Notre application
ne les écrit pas dans une base, un cookie, un journal ou des arguments de processus.
MT5 possède son propre stockage local : protéger les dossiers et l'utilisateur Windows.
Un vérificateur scrypt reste en mémoire pendant la vie du moteur ; après changement de
mot de passe, arrêter/revérifier et redémarrer l'hôte. Sessions web : 12 heures maximum.
Fermer la session ne stoppe pas un moteur autonome ; utiliser Arrêter avant de quitter
si l'on veut bloquer les nouvelles entrées. Arrêter ne liquide pas les positions ouvertes.

L'isolation est par processus et dossier, pas par machine virtuelle ou utilisateur Windows.
Un administrateur ou un processus compromis avec ses droits peut atteindre les terminaux.
Pilote pour un groupe de confiance, pas service public multi-client validé.
Pas de mesure de capacité réelle, haute disponibilité, service Windows, reprise automatique,
libération de place, rotation des mots de passe automatisée ou récupération de compte MT5.

## Tests et recette

```sh
python -m unittest discover -s hosted -p 'test_*.py' -v
node hosted/test-proxy.mjs
node --check hosted/proxy.mjs
```

Tests avec acteurs et MT5 simulés : sessions, CSRF, compte réel/investisseur refusé,
séparation des comptes, attribution automatique, pas de réservation après mot de passe
incorrect, saturation, serveurs non pris en charge et reprise des affectations sans secrets.

À vérifier sur Windows avant activation : login avec deux vrais comptes démo distincts,
soldes/commandes séparés, refus réel et investisseur, état des cotations, aucun démarrage
au login, Démarrer/Arrêter en démo, état inconnu en cas de coupure du tunnel, et redémarrage
sans perte des limites de risque. Aucun rendement ni passage d'ordre n'est revendiqué.
