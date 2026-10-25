# Diagnostic du moteur

Ajout de diagnostics en lecture seule : dernière bougie traitée (clôture UTC),
historique initial distinct des nouvelles bougies après démarrage, dernier cycle
réussi et étape réellement attendue d'après l'état du moteur. La réception d'une
réponse HTTP ne fait pas avancer ces compteurs. Un cycle n'est marqué réussi
qu'après lecture/traitement des bougies ; aucun cycle n'est inventé sur erreur.
Le compteur repart de zéro après Démarrer, l'historique initial est séparé.

Le tableau de bord indique les diagnostics indisponibles avec un ancien service
PC et signale un cycle de surveillance datant de plus de 15 secondes. Cela n'est
pas une preuve de rentabilité ou de bon comportement sur tous les marchés.

Validation : 50 tests connector, 16 tests hosted, test Node du tableau de bord,
test proxy, contrôles syntaxe et diff. MT5 simulé ; aucun ordre réel ni accès au
compte de Ben. Quatre nouveaux tests Python vérifient compteurs, absence de double
comptage, stades d'attente et absence de progression après erreur de cotation.

Installation : arrêter l'hôte, exécuter le script UPDATE_XAUUSD.ps1 existant qui
télécharge les fichiers actualisés de cette branche, relancer l'hôte avec la clé
existante. Garder Ngrok ouvert. Ne pas modifier les affectations ou états de risque.
Cette mise à jour ne modifie pas les règles d'entrée et ne démarre aucun moteur.
