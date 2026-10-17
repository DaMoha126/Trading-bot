# Livraison Trading Bot v4

Date de réalisation : 16 octobre 2026, après la demande de Ben de terminer la fiabilisation et de lui présenter un bilan le lendemain. Dépôt : https://github.com/DaMoha126/Trading-bot. Site : https://ben-bot-mt5.onrender.com. Le déploiement effectif est vérifiable dans Render ; ne pas confondre les tests locaux avec une session sur le PC utilisateur.

## Modifications réalisées

### Sauvegarde de la liaison

La liaison au PC n'est plus une simple variable en mémoire du serveur. URL et clé sont chiffrées AES-256-GCM dans un cookie HttpOnly/SameSite/Secure, pendant 30 jours. Une fois la nouvelle version reliée, la liaison peut survivre aux redémarrages de Render et à une nouvelle connexion au site. SESSION_SECRET doit rester stable.

Aucun service payant ni nouvelle base de données ajouté. La sauvegarde est par navigateur : un deuxième appareil doit être relié une fois. Un nouveau tunnel donne toujours une nouvelle URL/clé à recopier.

### Fermeture du site

Un choix **Continuer quand le site est fermé** est ajouté avant Démarrer. Sans le cocher, le mode supervisé conserve la pause après 25 secondes sans tableau de bord. Si coché, le moteur reste autonome sur le PC tant que PC/MT5/connecteur restent actifs. Le service Render n'exécute pas MT5.

Le connecteur démarre toujours à l'arrêt après un redémarrage du processus. Les erreurs de données, compte réel/concours, compte changé, risque quotidien atteint et réponses d'ordre incertaines restent bloquantes. Arrêter bloque les nouvelles entrées mais ne liquide pas les positions existantes ; leurs SL/TP restent chez le courtier.

### Historique et bilan des trades

Lecture des deals MT5 sur 90 jours et regroupement par identifiant de position, avec déduplication des tickets. Commissions d'entrée/sortie, swaps et frais rattachés sont intégrés au résultat net. Les sorties partielles sont réunies dans une position complète. Les positions encore ouvertes ne sont pas comptées dans le résultat réalisé.

Les clôtures manuelles d'une position du bot sont incluses. Les positions avec ajout manuel ou renversement sont exclues pour éviter d'attribuer leurs résultats au bot. Les historiques incomplets sont signalés. Les frais globaux sans identifiant de position ne sont pas affectés.

L'interface affiche les 500 dernières positions clôturées disponibles, filtre BUY/SELL, résultat net, réussite, nombre de positions et espérance. Le CSV suit le filtre, le rapport JSON contient le bilan récupéré, avec ventilation quotidienne et par sens. Une éventuelle limite de 500 positions est annoncée.

### Courbe d'equity

Le connecteur v4 conserve sur le PC jusqu'à 2 880 relevés, espacés d'au moins 30 secondes et sauvegardés toutes les 60 secondes au plus. Les relevés peuvent être repris après redémarrage et séparent les comptes. Il ne s'agit pas d'un historique au tick près. Une coupure brutale peut perdre les derniers relevés non enregistrés.

### Backtest et bougies du compte connecté

La source **MT5 — historique du compte connecté** lit jusqu'à 10 000 bougies M3 clôturées depuis le terminal. Accès direct depuis le bilan du tableau de bord. Cette lecture n'envoie aucun ordre. Si MT5 est indisponible, le site affiche une erreur sans remplacer les prix par des données artificielles.

Le laboratoire garde la démo synthétique, l'import CSV, le partage chronologique 70/30 et les exports. Les résultats sur historique MT5 restent des simulations avec modèle de coûts configurable.

### Fiabilité et interface

- Statut « État inconnu » lorsque le PC ne répond plus, au lieu de prétendre que le bot est arrêté.
- Dissociation avec avertissement si l'arrêt distant n'est pas confirmé, particulièrement en mode autonome.
- Ancienne version du connecteur détectée : historique/mode autonome exigent la v4.
- Remplacement de PC protégé par une tentative d'arrêt de l'ancien connecteur.
- Limite quotidienne conservée séparément par compte, même après changement de compte puis retour.
- Métadonnées de prix/volume invalides et ticks futurs/périmés refusés avant envoi.
- Mémoire du moteur bornée pour les sessions prolongées.
- Ancre manquante du tableau de bord corrigée après liaison réussie.
- Nouveau paquet Windows v4, guide mis à jour, démarrage du tunnel après vérification du connecteur et du compte démo, ouverture automatique du site Render.

## Vérifications exécutées

1. **39 tests Python réussis**, avec faux terminal MT5 : les 18 précédents et 21 nouveaux tests d'historique, autonomie, persistance des relevés, données invalides et état de risque.
2. **Six suites JavaScript réussies via npm test** : chiffrement/persistance de liaison, relais sécurisé/version/candles, origine HTTPS et cookie de session, routes privées et identifiants DOM, rendu logique autonome/inconnu/historique, parité Python/JavaScript du backtest.
3. La référence de démonstration conserve 16 transactions avec prix, taille, sorties, résultat net et drawdown identiques entre moteurs Python et JavaScript. Prix synthétiques, aucune preuve de rentabilité.
4. Vérifications de syntaxe JavaScript/Python, différences Git sans erreurs d'espacement, intégrité du ZIP v4, absence d'état de compte ou de secrets dans le paquet.
5. Publication Render et contrôles HTTP du site à vérifier en fin de livraison : page de connexion, route de santé et refus de l'API sans session. Le bilan du lendemain doit contrôler le statut réel du dernier déploiement.

## Ce qui n'a pas été fait et reste à valider

- Aucun ordre envoyé à un compte utilisateur. Aucun bot activé pendant le travail.
- Aucune installation Windows réelle ni connexion au terminal MT5 de Ben : sa machine et son compte ne sont pas accessibles ici.
- Aucun backtest sur des données réelles de son courtier ; l'outil pour le faire est prêt, mais le jeu de données n'a pas été reçu.
- Aucun rendement ni taux de réussite de marché validé. Aucun contrôle visuel dans un navigateur réel revendiqué ; les tests d'interface exécutent la logique avec un DOM simulé.
- Le tunnel gratuit peut changer ou tomber ; le PC doit rester allumé. Aucun VPS Windows ni abonnement ajouté.

## Étapes pratiques pour Ben

1. Ouvrir Trading Bot et, si nécessaire, se reconnecter avec son mot de passe actuel (inchangé).
2. Télécharger **Trading_Bot_Connecteur_v4.zip**, fermer l'ancien connecteur et installer la nouvelle version. Si une version précédente a déjà servi, conserver/copier `risk_state.json` et `risk_state_equity.json`.
3. Ouvrir MT5 sur un compte démo USD puis lancer le connecteur. Copier la nouvelle URL/clé sur le site ; vérifier le compte affiché.
4. Vérifier d'abord les positions et l'historique, puis lancer un backtest avec la source MT5. Un marché fermé ou des données périmées peuvent empêcher le démarrage du bot : c'est attendu.
5. Pour un premier essai d'exécution, choisir le mode supervisé. Le mode autonome est disponible explicitement lorsque la chaîne MT5 et les protections sont confirmées en démo.
