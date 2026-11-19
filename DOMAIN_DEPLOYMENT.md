# Domaine saneahair.com

Publication autorisée sur le domaine de l'utilisateur, via GitHub Pages et Cloudflare.

- http://saneahair.com/ : HTTP200 ; http://www.saneahair.com/ redirige vers l'apex.
- Au contrôle du19 novembre2026, HTTPS n'est pas encore disponible : certificat présenté ne couvrant pas les noms, curl code60. Ne pas ignorer l'alerte TLS. HTTPS non forcé avant certificat valide.
- Pages legacy, gh-pages:/, CNAME saneahair.com ; commit statique ed50bb73dfe08b4440b45015c08af8aa0f561797,84 fichiers.
- Apex et www : CNAME ifouedaniel-jpg.github.io sans proxy, apex aplati Cloudflare. Aucun autre enregistrement ni réglage de sécurité modifié.
- Build racine préparé utilisé sans reconstruction. Canonical https://saneahair.com, aucun ancien préfixe /memoire237/.
- QA publique sur HTTP :75 routes,225 reflows320/390/1440,4 recherches,60 filtres,84 fichiers identiques SHA256, zéro erreur JS/HTTP.29 tests unitaires et compilation réussis. Cela ne constitue pas une QA HTTPS réussie.
- Corpus inchangé37 événements,7 personnes dont un collectif,10 lieux,9 thèmes,1 parcours ; limites éditoriales maintenues.

Une fois TLS prêt, vérifier200 avec validation de certificat sur apex et www, activer enforce_https et relire Pages avant nouvelle QA HTTPS. Sauvegarde DNS complète et procédure de rollback conservées séparément, privées. Aucune preuve historique ou donnée interne n'est distribuée.
