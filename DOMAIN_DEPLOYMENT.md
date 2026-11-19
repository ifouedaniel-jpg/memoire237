# Domaine saneahair.com — HTTPS vérifié le 19 novembre 2026 UTC

Publication autorisée via GitHub Pages et Cloudflare ; édition documentaire partielle inchangée.

- **https://saneahair.com/** : TLS valide, HTTP200. www HTTPS redirige vers l’apex ; HTTP apex/www redirige vers HTTPS, destination200.
- État natif GitHub Pages relu : certificat `approved` pour apex et www, expiration annoncée `2027-02-17`, `https_enforced:true`, build `built`, source `gh-pages:/`, mode `legacy`.
- Après un blocage de provisioning, le domaine personnalisé a été retiré puis réajouté par l’API officielle GitHub. GitHub a créé le commit statique `a2f954509a86df8d910abde29f8576a58eb971d8`, normalisant uniquement CNAME en `saneahair.com` sans saut de ligne final.
- Arbre exact84 fichiers vérifié par hashes :83 blobs inchangés. Seul le chemin racine CNAME accepte exactement `saneahair.com` avec zéro ou un LF final ; aucun autre hôte, espace, CRLF ou ligne supplémentaire. Les SHA256 des83 autres fichiers restent stricts. Le site n’a pas été modifié pour satisfaire le test.
- QA publique **sur HTTPS** :75 routes,225 reflows320/390/1440,475 citations réellement cliquées,60 filtres,4 recherches,84 fichiers contrôlés, zéro erreur JS/HTTP. **32 tests unitaires réussis**, compilation réussie. Captures accueil mobile/desktop inspectées sans chevauchement manifeste. L’échec CNAME initial et les tests rouges sont conservés séparément, privés.
- Corpus accepté inchangé :37 événements,7 personnes dont un collectif,10 lieux,9 thèmes,1 parcours ;75 pages,25 sources. Aucun rebuild ni changement éditorial.
- DNS existant : apex/www vers GitHub sans proxy. Aucun changement DNS, certificat, proxy, service système ou Hermes pendant cette clôture QA.

Les preuves natives API, rapports QA, sauvegardes et procédure de rollback sont privés et ne sont pas distribués. Reconstruire le corpus exige ses entrées et preuves originales ; ne pas contourner leur validation. Audit manuel accessibilité, disponibilité distante des sources et validation historienne restent ouverts ; aucun nouvel audit axe n’est revendiqué.
