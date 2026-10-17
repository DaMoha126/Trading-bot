# Trading Bot v4

Poste de commande privé EUR/USD M3 et laboratoire de backtest. Le moteur MT5 tourne sur le PC Windows de l'utilisateur ; Render héberge l'interface et le relais HTTPS. Comptes MT5 de démonstration en USD uniquement.

## Routes et composants

- `/control.html` : compte, cotations, Démarrer/Arrêter, supervision, positions, historique et exports.
- `/api/bridge` : relais HTTPS authentifié vers le connecteur du PC. Aucun mot de passe MT5 demandé.
- `/lab/index.html` : démo synthétique, import CSV, historique réel MT5, partage chronologique 70/30 et rapports simulés.
- `connector/` : moteur démo, récupération des bougies et des exécutions, protections et tests avec faux terminal.

## Liaison qui survit aux redémarrages du site

L'URL et la clé du connecteur sont chiffrées avec AES-256-GCM et conservées dans un cookie HttpOnly, SameSite=Strict, Secure en HTTPS, valide 30 jours. Aucun secret n'est renvoyé dans les réponses JSON. La variable `SESSION_SECRET` doit rester stable sur Render. Les connexions au site durent 12 heures ; se reconnecter au site ne nécessite pas de relier le PC si le cookie de liaison reste valide.

La sauvegarde est propre à chaque navigateur/appareil. Un téléphone doit être relié une fois séparément. Effacer les cookies, changer `SESSION_SECRET` ou relancer le tunnel avec une nouvelle URL nécessite une nouvelle liaison. Il n'y a ni base payante ni synchronisation centrale multi-appareils.

Le serveur n'accepte que des endpoints HTTPS `*.trycloudflare.com`, sans redirection, ni chemin arbitraire. Le remplacement d'un ancien connecteur exige son arrêt confirmé ; si l'ancien PC est injoignable, la dissociation explicite prévient que le bot autonome peut encore tourner.

## Mode supervisé et mode autonome

Le mode par défaut est supervisé : plus de 25 secondes sans contact du tableau de bord = pause des nouvelles entrées.

Cocher **Continuer quand le site est fermé** avant Démarrer active le mode autonome. Le PC, MT5 et le connecteur doivent rester allumés. Le moteur local poursuit les recherches et les contrôles du risque sans dépendre du navigateur ou de la veille de Render. Une coupure de tunnel peut empêcher l'arrêt distant ; arrêter le connecteur sur le PC si nécessaire. Les SL/TP existants restent chez le courtier.

Un redémarrage du connecteur ne relance jamais automatiquement les ordres. Compte changé, données périmées, réponse d'ordre incertaine ou limite quotidienne atteinte = arrêt/pause des nouvelles entrées. L'identifiant du dernier signal est écrit avant envoi pour éviter les renvois aveugles.

## Historique et résultats nets

Le connecteur lit les deals MT5 sur 90 jours et reconstruit les positions du MagicNumber du bot. Les entrées et sorties partielles sont regroupées par identifiant de position. Une clôture manuelle d'une position du bot est incluse ; un ajout manuel à cette position ou un renversement la rend mixte et l'exclut des statistiques. Les doublons d'exécution sont dédupliqués par ticket.

Le net comprend profit + commissions + swap + frais rattachés aux deals. Les commissions globales sans position associée ne peuvent pas être allouées. Les positions ouvertes et les historiques incomplets sont exclus du résultat réalisé. Les fenêtres peuvent manquer des opérations si le courtier limite son historique ; le logiciel ne reconstitue aucun prix manquant.

Les 500 positions clôturées les plus récentes sont transmises à l'interface. La troncature éventuelle est signalée. Les métriques affichées et le CSV portent sur cette liste et le filtre de sens sélectionné. Le JSON contient aussi le bilan par jour et par sens calculé sur l'historique complet récupéré, avant cette limitation d'affichage.

La courbe d'equity est relevée localement toutes les 30 secondes au plus et conserve 2 880 observations. Le fichier local est sauvegardé au plus toutes les 60 secondes : une extinction brutale peut perdre les derniers relevés, sans réinitialiser la limite de risque enregistrée séparément. La courbe représente des observations, pas une reconstitution de chaque tick.

## Backtest réel via MT5

Depuis l'historique, **Tester l'historique M3 du compte** ouvre le laboratoire sur la source MT5. Le connecteur exporte jusqu'à 10 000 bougies BID M3 clôturées. L'index 0 en formation est exclu. Une demande de bougies n'ouvre aucun ordre. Aucun repli silencieux vers des données artificielles si MT5 n'est pas disponible.

Les exécutions et les coûts du backtest restent simulés. Configurer spread, glissement et commissions en cohérence avec le courtier. Le spread du CSV/MT5 est une différence de prix ASK−BID ; le réglage de spread de l'interface est une valeur de secours si la colonne est absente. L'évaluation des 30 % finaux utilise un compte et des indicateurs neufs, sans transfert d'une position de la période précédente.

## Déploiement et secrets

Node 22, sans dépendance npm. `Dockerfile` et `render.yaml` sont fournis. Le dépôt GitHub déclenche automatiquement Render.

- `APP_PASSWORD` : mot de passe du site, au moins 16 caractères.
- `SESSION_SECRET` : secret stable de signature/chiffrement.
- `PUBLIC_URL` : origine publique HTTPS facultative, prioritaire si renseignée.
- `RENDER_EXTERNAL_URL` : origine publique automatiquement fournie par Render, utilisée avant tout hôte interne du proxy.
- `PORT` : fourni par l'hébergeur.

La politique de référent `same-origin` préserve l'origine des formulaires tout en masquant les référents intersites. Les origines absentes, nulles ou étrangères sont refusées. Aucun secret ou état de compte ne doit être commis dans Git.

## Tests exécutables

```sh
npm test
python -m unittest discover -s connector -p 'test_*.py'
```

`npm test` vérifie chiffrement/persistance de la liaison, relais/version du connecteur, contrôle d'origine derrière HTTPS, sessions et accès privés, rendu logique du tableau de bord, et parité du backtest JavaScript avec la référence Python.

Les tests Python utilisent un faux terminal et couvrent comptes réels/concours, risque, ordres uniques, reprises, modes supervisé/autonome, données invalides, exports de bougies, historique et relevés d'equity. Ils n'ont envoyé aucun ordre à un courtier.

Voir `NIGHTLY_REPORT.md` pour la livraison du 16 octobre. La validation sur Windows, le tunnel réel du PC, l'historique réel de l'utilisateur et les exécutions du courtier restent à effectuer sur compte démo. Aucun test de rentabilité sur marché réel ni contrôle visuel dans un navigateur n'est revendiqué.
