# Trading Bot — connecteur Windows v4

## Première installation

1. Installer Python 3.10+ 64 bits avec le lanceur `py`, puis ouvrir MetaTrader 5 sur un compte **DEMO en USD**.
2. Activer Algo Trading et autoriser le trading via API Python externe dans les options de MT5.
3. Extraire ce ZIP et lancer `INSTALLER_ET_LANCER.bat`. L'installation crée un environnement Python local, installe MetaTrader5 et peut installer Cloudflare Tunnel via winget.
4. Le lancement vérifie le compte démo avant d'ouvrir le tunnel, puis affiche URL et clé de liaison. Elles ne sont pas des identifiants MT5 ; ne pas les publier.
5. Ouvrir https://ben-bot-mt5.onrender.com et relier le PC avec ces deux valeurs. Vérifier le compte affiché avant de cliquer sur Démarrer.

Pour les démarrages suivants : `LANCER.bat`. Si cloudflared vient d'être installé mais reste introuvable, fermer la fenêtre puis relancer. Un seul connecteur doit utiliser le port 8765. Si plusieurs terminaux MT5 sont installés, vérifier le numéro de compte affiché avant Démarrer.

## Mise à jour

Arrêter le bot et fermer l'ancien connecteur. Installer les nouveaux fichiers dans le même dossier ou recopier l'ancien `risk_state.json` et `risk_state_equity.json` dans le nouveau dossier. **Ne pas supprimer l'état de risque pour contourner le verrou quotidien.** L'ancienne version peut avoir un dossier nommé Ben_MT5_Demo_Connecteur ; les fichiers d'état restent compatibles.

## Fermer le navigateur

Le mode par défaut est supervisé : pause après 25 secondes sans tableau de bord actif.

Le mode autonome s'active en cochant **Continuer quand le site est fermé**, avant Démarrer. Le PC, MT5 et cette fenêtre doivent rester ouverts. Render ou le navigateur peuvent alors être fermés/mis en veille sans arrêter le moteur local. Un tunnel coupé empêche les commandes distantes ; intervenir sur le PC si nécessaire.

Arrêter bloque les nouvelles entrées ; les positions ouvertes conservent leurs SL/TP. Une fermeture de cette fenêtre stoppe le moteur. Un relancement démarre toujours à l'arrêt, même si le mode précédent était autonome.

## Historique et sauvegardes

- `risk_state.json` : limites quotidiennes séparées par compte, dernier signal envoyé, dernière configuration. Écriture atomique.
- `risk_state_equity.json` : jusqu'à 2 880 observations d'equity, sauvegardées toutes les 60 secondes au plus.
- `journal.jsonl` : décisions et anomalies locales.
- Historique des trades : relu auprès de MT5, regroupé par position sur 90 jours, avec commissions/swap/frais associés et sorties partielles. Au plus 500 positions récentes affichées et exportées en CSV ; les limites sont signalées.

Les positions modifiées par des ajouts manuels sont exclues du bilan pour éviter d'attribuer leurs résultats au bot. Les clôtures manuelles seules sont prises en compte.

La liaison au PC est conservée chiffrée dans le navigateur 30 jours et survit au redémarrage du serveur Render tant que SESSION_SECRET reste stable. Un autre appareil doit être relié séparément. Chaque nouveau lancement du tunnel change l'URL/la clé : relier à nouveau.

## Stratégie et limites

EUR/USD M3, CHoCH → retest → prise de liquidité → rejet. Bougies clôturées uniquement, pivots 2/2 confirmés avec retard, ATR14 arithmétique, largeur totale de zone 0,15 ATR, mèche minimale 40 %, expiration 20 bougies, stop au-delà de la mèche avec marge 0,1 ATR.

Risque par défaut 0,5 %, limite quotidienne 1 %, ratio brut 1:2. Plafonds de test : risque 1 % et limite quotidienne 3 %. Une seule position/un seul ordre sur le compte ; aucun empilement ni martingale. Une clôture de signal de plus de 30 secondes n'est plus exécutée. La taille respecte le pas/minimum du courtier, les frais estimés et la marge disponible. Les gaps peuvent dépasser le risque prévu.

Compte réel/concours et compte non-USD refusés. Type du compte vérifié immédiatement avant chaque envoi/modification. Si la réponse d'un ordre est incertaine, le moteur s'arrête sans répéter automatiquement l'ordre. Vérifier MT5 avant de relancer.

La source MT5 du laboratoire exporte jusqu'à 10 000 bougies clôturées ; cette lecture est sans ordre. L'historique ne constitue pas une garantie de rentabilité. Un marché fermé ou un tick périmé provoque un refus/pause des nouvelles entrées.

## Vérification

Tests automatisés avec terminal simulé. Aucun compte utilisateur ni courtier n'a été utilisé par ces tests. Installation Windows, tunnel du PC et exécutions chez le courtier restent à vérifier en démo.

Références :
- https://www.mql5.com/en/docs/python_metatrader5/mt5ordersend_py
- https://www.mql5.com/en/docs/python_metatrader5/mt5historydealsget_py
- https://developers.cloudflare.com/tunnel/get-started/quick-tunnels/
