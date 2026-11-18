# Publication statique

Site : https://ifouedaniel-jpg.github.io/memoire237/

Pages utilise `build_type: legacy`, branche `gh-pages`, chemin `/` et HTTPS GitHub.
Aucun workflow Actions personnalisé. Aucun domaine personnalisé ni abonnement.
L’instantané est généré après validation stricte des preuves privées originales,
puis testé sous `/memoire237/` : navigation, assets, recherche, filtres, citations,
reflow 320/390/1440. `.nojekyll` conserve les fichiers statiques ; `404.html` est
la page d’erreur GitHub Pages. Les canonical, OG, JSON-LD, sitemap, URLs de recherche
et assets incluent le sous-chemin. Le serveur de développement reste loopback.

La politique `robots.txt` reste prudente (Disallow) : accès par lien, sans demande
d’indexation des moteurs pour cette édition partielle. Sur un site GitHub Pages de
projet, le robots.txt de sous-répertoire ne contrôle pas nécessairement les robots
à l’échelle du domaine. Il n’est en aucun cas une protection d’accès : le site et
le dépôt sont publics. Les en-têtes CSP du serveur Python local ne sont pas
transposés automatiquement à GitHub Pages.

Pour une mise à jour, conserver les preuves originales privées, reconstruire,
réexécuter les tests, exporter uniquement les sorties attendues et contrôler
l’absence de chemins privés/secrets. Ne jamais exporter un ZIP de sauvegarde ni
faire un ajout global de la racine du projet. Ne pas publier les téléchargements.
Les liens externes cités sont documentés mais leur disponibilité future n’est
pas garantie. La validation historienne, la complétude du corpus et un audit
manuel complet d’accessibilité restent à réaliser.
