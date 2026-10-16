# Ben Bot V3 — hébergement indépendant

Interface mobile inspirée de la vidéo fournie : noir profond, titres et courbe dorés, état de connexion turquoise, bloc MT5 Account, étapes d'analyse et boutons Démarrer/Arrêter. Les valeurs restent absentes jusqu'à réception des données du compte démo. Aucune fausse animation de résultat.

## Hébergement externe

Application Node 22 sans dépendance npm. `Dockerfile` et `render.yaml` inclus pour déploiement hors de ChatGPT Sites. Il faut un compte d'hébergement connecté et, selon la plateforme, un dépôt Git accessible. Aucun déploiement externe n'a été réalisé dans ce paquet.

Sur Render, utiliser le Blueprint `render.yaml` depuis le dépôt contenant ce dossier comme racine de l'application. Le mot de passe `APP_PASSWORD` et la clé `SESSION_SECRET` sont générés par l'hébergeur ; consulter la variable APP_PASSWORD dans son espace privé pour se connecter. Ne pas publier ces valeurs. Si l'application est dans un sous-dossier d'un dépôt existant, le choisir comme répertoire racine du service.

Variables :
- `APP_PASSWORD` : mot de passe privé, au moins 16 caractères, obligatoire.
- `SESSION_SECRET` : clé aléatoire de session, recommandée pour préserver les connexions entre redémarrages.
- `PUBLIC_URL` : origine HTTPS exacte facultative, à renseigner si l'hébergeur présente un domaine différent dans l'en-tête Host.
- `PORT` : port fourni par l'hébergeur, 3000 par défaut.
- `NODE_ENV=production` : cookies sécurisés HTTPS.

La liaison au connecteur est conservée en mémoire serveur : après redémarrage ou mise en veille du service, relier à nouveau le PC. Déployer une seule instance pour ces essais. Les offres qui mettent le service en veille ne conviennent pas à un fonctionnement sans surveillance. Le bot met les nouvelles entrées en pause après 25 secondes sans contact.

## Installation MT5

Le ZIP du connecteur est disponible dans l'interface. L'extraire sur un PC Windows où Python 3.10+ et MT5 sont installés. Compte DEMO en USD uniquement. Ouvrir le nouveau site externe dans un navigateur après lancement du connecteur et y coller URL et clé de liaison. Le mot de passe MT5 reste dans le terminal.

Le connecteur démarre à l'arrêt. Lancer le bot exige le bouton Démarrer. Arrêter suspend uniquement les nouvelles entrées ; stops et objectifs existants restent au courtier. PC, connecteur et tableau de bord doivent rester actifs.

## Essai local

Définir APP_PASSWORD (au moins 16 caractères) puis `node server.mjs`. Ouvrir http://localhost:3000. Garder NODE_ENV différent de production pour cet essai HTTP local. Ne pas exposer de compte réel.

## Vérifications

Le moteur et le connecteur démo conservent les règles précédentes. Le test du serveur vérifie le refus sans authentification, l'ouverture de session, l'accès à l'interface, l'isolation des fichiers et les contrôles de la liaison. Aucun essai sur un terminal MT5 réel ni contrôle visuel dans un navigateur n'a été effectué ici.
