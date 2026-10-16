# Ben Forex Lab — connecteur MT5 démo

## Installation Windows

1. Installer Python 3.10+ 64 bits avec son lanceur `py` et MetaTrader 5.
2. Dans MT5, ouvrir un compte **DEMO en USD**. Activer Algo Trading et, dans les options Expert Advisors, autoriser le trading via l'API Python externe.
3. Extraire le ZIP. Lancer `INSTALLER_ET_LANCER.bat`. Ce script crée un environnement Python local, installe le module MetaTrader5 et, si nécessaire, Cloudflare Tunnel via winget.
4. Copier l'URL de liaison HTTPS et la clé affichées dans « Connecter mon PC » sur le site privé. Ces valeurs sont des secrets de liaison : ne pas les publier.
5. Vérifier le numéro du compte affiché, régler le symbole exact EURUSD (suffixes courtier acceptés), puis cliquer sur **Démarrer**.

Pour les lancements suivants : `LANCER.bat`. Si winget vient d'installer cloudflared et que celui-ci reste introuvable, fermer la fenêtre et relancer. L'URL et la clé changent à chaque lancement. Le mot de passe MT5 reste dans le terminal, il n'est jamais demandé par le site.

Site : Ton nouveau domaine externe (après déploiement)

## Fonctionnement

Le site privé conserve côté serveur l'URL et la clé de liaison, associées à l'utilisateur connecté. Le connecteur écoute uniquement sur 127.0.0.1:8765 et exige la clé pour toute lecture ou commande. Cloudflare fournit le tunnel HTTPS temporaire. Aucun port entrant du routeur à ouvrir. Ce tunnel gratuit est prévu pour des essais et peut être interrompu ; reconnecter avec la nouvelle URL si nécessaire.

Le PC, MT5 et le connecteur doivent rester allumés. Le tableau de bord contacte le PC toutes les cinq secondes. Après 25 secondes sans contact, le bot suspend les nouvelles entrées ; il faut cliquer à nouveau sur Démarrer. Sur téléphone, la mise en veille ou le navigateur en arrière-plan peut provoquer cette pause. **Arrêter ne ferme pas les positions existantes** : leurs SL/TP restent chez le courtier. Fermer les positions manuellement dans MT5 si souhaité.

Le connecteur envoie des ordres réels **sur le serveur de démonstration**, sans argent réel. Comptes réels et concours rejetés, type du compte revérifié immédiatement avant chaque envoi/modification. Seule la paire EUR/USD et un compte USD sont pris en charge. Le bot est à l'arrêt au lancement du processus. Une position ou un ordre déjà présent sur le compte bloque toute nouvelle entrée, même d'origine manuelle.

## Stratégie et risque

Moteur CHoCH, retest et rejet de la V1. Bougies M3 clôturées, pivots confirmés avec deux bougies de retard. Largeur totale de zone 0,15 ATR14, mèche minimale 40 %, délai de 20 bougies, marge de stop 0,1 ATR. Signal rejeté si une entrée fraîche n'est plus possible dans les 30 secondes suivant la clôture. Aucun signal historique exécuté au démarrage.

Risque par défaut 0,5 %, limite quotidienne 1 %, ratio brut 1:2. Paramètres éditables depuis le site ; plafonds de test : risque 1 % et limite quotidienne 3 %. Stop et cible transmis avec l'ordre d'entrée. Cible ensuite ajustée au prix d'exécution si le courtier l'accepte ; sinon la cible initiale est conservée et une alerte apparaît. Les coûts modélisés pour la taille incluent la commission estimée (3,50 USD/lot/côté) et une réserve de glissement ; ils doivent être adaptés au courtier avant toute analyse de performance.

Les gaps/exécutions peuvent dépasser le risque prévu. Le verrou quotidien repose sur l'equity du compte entier et sa référence à la première observation du jour UTC. Ne pas supprimer `risk_state.json` pendant la journée : il conserve le verrou et le dernier signal envoyé. Un changement de compte met le bot en pause ; relancer le connecteur pour changer de compte démo. Aucune martingale ni empilement.

Chaque signal est marqué comme envoyé avant appel à MT5 pour éviter de rejouer un ordre après réponse incertaine. Une réponse incertaine arrête le bot ; inspecter MT5 avant de redémarrer. Le bot ne répète pas automatiquement l'ordre. Les rejets et erreurs sont dans `journal.jsonl` et le tableau de bord.

## Vérification et limites

Les tests automatisés utilisent un faux terminal, sans accès à un compte. L'installation Windows, la liaison HTTPS sur ton PC et les exécutions chez ton courtier restent à vérifier sur compte démo. Aucune rentabilité ni exécution continue n'est garantie. Le navigateur doit rester actif pendant ces premiers essais.

Références :
- https://www.mql5.com/en/docs/python_metatrader5/mt5ordersend_py
- https://www.mql5.com/en/docs/python_metatrader5/mt5accountinfo_py
- https://developers.cloudflare.com/tunnel/get-started/quick-tunnels/
