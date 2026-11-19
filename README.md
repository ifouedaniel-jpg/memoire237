# MÉMOIRE 237

**Consulter le site : http://saneahair.com/** — domaine personnalisé configuré ; www redirige vers l’apex. HTTPS reste en attente d’un certificat GitHub couvrant les noms au dernier contrôle (curl60) ; ne pas ignorer l’alerte TLS. Voir [DOMAIN_DEPLOYMENT.md](DOMAIN_DEPLOYMENT.md).

Musée numérique français consacré à l’histoire du Cameroun. Édition documentaire
partielle : 37 événements, six portraits individuels partiels et un collectif,
dix lieux, neuf thèmes et un parcours ; 75 pages, 25 sources bibliographiques.
Objectifs éditoriaux complets non atteints, lacune 1972–1982, relecture assistée par
agents sans validation historienne. Ces limites sont également visibles sur le site.

## Organisation publique

- `main` : code Python standard, assets HTML/CSS/JS et tests ; documentation technique.
- `gh-pages` : instantané statique validé, servi par GitHub Pages à la racine de cette branche.
- Domaine personnalisé saneahair.com, DNS Cloudflare vers GitHub Pages sans proxy ; aucun workflow Actions personnalisé ou service payant configuré.

Les corpus JSON internes, notices non acceptées, téléchargements documentaires,
PDF et textes de preuves, rapports internes, mémoires personnelles, sauvegardes,
logs et données d’exécution ne sont **pas** distribués. Les sources originales sont
référencées dans les pages publiques, sans redistribution des téléchargements.
Aucune licence générale des textes historiques ou sources tierces n’est revendiquée.
L’absence de fichier LICENSE ne constitue pas une autorisation de réutilisation.

## Développement

Python 3.11+, aucune dépendance applicative.

```sh
python3 -m unittest discover -s tests -v
python3 -m compileall -q scripts tests
python3 scripts/build.py
python3 scripts/serve.py --port 8237
```

Sans `research/corpus.json`, le build produit une édition vide honnête : il ne peut
pas reconstruire les 75 pages du site à partir de ce seul dépôt public. La branche
`gh-pages` conserve l’instantané publié. Reconstruire le corpus réel exige le corpus
accepté et ses preuves locales originales, conservés séparément par le responsable
éditorial. Une preuve absente fait échouer le build : ne pas désactiver ce contrôle,
ne pas créer des preuves fictives ni recopier l’index de recherche comme corpus.

Pour générer les URLs GitHub Pages avec ces entrées privées présentes :

```sh
python3 scripts/build.py --base-url https://ifouedaniel-jpg.github.io/memoire237
```

La configuration par défaut reste locale (127.0.0.1:8237). Ce build remplace `dist/`
par une sortie pour sous-chemin ; refaire `python3 scripts/build.py` avant de
reprendre la prévisualisation à la racine locale. Ne servir que `dist/`, jamais la
racine du dépôt. Les tests utilisent des fixtures explicitement fictives et isolées.
Les QA navigateur optionnelles exigent les outils `.qa/`, non versionnés ;
`qa_real_corpus.py` et `qa_pages.py` exigent en outre le corpus accepté privé.

Voir [ARCHITECTURE.md](ARCHITECTURE.md), [CONTENT_MODEL.md](CONTENT_MODEL.md),
[contrat documentaire](docs/CONTENT_CONTRACT.md) et [DEPLOYMENT.md](DEPLOYMENT.md).
