# Architecture

## Choix

Générateur statique Python + JavaScript natif, plutôt que Next.js. Node/npm absents au démarrage ; pas de besoin utilisateur justifiant une chaîne React, un backend ou une installation système. La bibliothèque standard suffit à la validation, aux pages pré-rendues, au serveur loopback et aux sauvegardes. Le site fonctionne hors réseau après build. Les outils Playwright/Chromium/axe sont optionnels, locaux au projet et non requis par l’application.

## Flux et frontières de confiance

```text
research/corpus-candidate.json  ── revue documentaire Master ──> research/corpus.json
       (jamais lu au build)                                      │ privé
                                                                ▼
site_config.json + scripts/build.py + assets/ ─ validation ─ filtrage publication
                                                                │
                                                                ▼
                              dist/ : HTML + CSS + JS + index public + sitemap
                                                                │
                                         scripts/serve.py : 127.0.0.1 uniquement
```

- `research/` : propriété documentaire ; jamais modifié par le générateur, jamais copié ni servi.
- `scripts/build.py` : schéma et intégrité référentielle, gate `publie && reviewed is True`, pages statiques, relations directes/inverses, carte, index et métadonnées. Construit dans un staging neuf puis remplace uniquement un `dist/` marqué `build-report.json`. Une validation échouée laisse le build précédent intact. Le remplacement local comporte une brève fenêtre sans dossier ; ne constitue pas une stratégie de déploiement atomique multi-instance.
- `assets/` : seuls `style.css`, `app.js`, `icon.svg` sont admis. Texte du corpus échappé ; aucun HTML/Markdown brut de confiance. DOM de recherche créé avec textContent, jamais innerHTML des données.
- `scripts/serve.py` : document root fixe `dist/`, whitelist d’assets/JSON, pages HTML, pas de listing, refus chemins privés, dotfiles et symlinks. 404 neutre ; CSP restrictive, nosniff, no-referrer, pas d’encadrement. Le rapport de build n’est pas servi. Ce serveur de développement n’est ni un serveur Internet de production ni une sandbox contre un attaquant local pouvant réécrire le dépôt.
- `scripts/manage.py` : démarrage détaché, port libre optionnel, nonce et vérification `/proc/PID/cmdline` avant signal ; verrou local des commandes de gestion. Ne touche qu’au processus de ce projet. Sauvegarde/restauration vers copie, manifest SHA256, limites de taille et chemins.
- `.run/`, `.qa/`, `backups/`, `restored/`, `evidence/` : privés et hors docroot, ignorés par Git selon leur nature. Le serveur ne peut pas les parcourir.

## Navigation et données

Toutes les fiches et listes sont HTML pré-rendu. Les filtres modifient `hidden` sur les cartes ; recherche à la demande dans un index JSON minimal des seules fiches publiques. Termes normalisés NFD, accents/casse supprimés, œ/æ normalisés, AND par mots. Pas de recherche sémantique ni correction orthographique. Pas de serveur de recherche, cookies, compte ou télémétrie.

Les citations [N] sont reliées au citationNumber persistant de la source, jamais à sa position dans une bibliographie locale ; les références non déclarées dans sourceIds bloquent la publication. editorialNote est rendu comme texte échappé dans chaque fiche. entryType/category distingue les collectifs ; une déclaration « Portrait partiel » dans editorialNote étiquette aussi la carte individuelle. Les avertissements d’accueil/méthode sont calculés depuis les fiches publiques. Les h1 documentaires autorisent la rupture des mots trop longs, sans clipping global. QA réelle séparée des fixtures : tests/qa_real_corpus.py ; diagnostic ciblé 320 px : tests/qa_reflow_regression.py.

Relations réciproques calculées à partir des IDs, en ignorant seulement les cibles **valides mais non publiques** au rendu. Une cible inexistante reste une erreur de build, même dans un brouillon. Les parcours incomplets sont retirés, pas tronqués. Les slugs restent les identifiants d’URL ; ne pas les changer sans future politique de redirection.

## Dates et carte

Les années de début/fin servent au tri et au filtre inclusif. Le libellé documentaire est affiché sans invention de jour. Les neuf périodes sont des instruments de lecture, pas une interprétation unique de toutes les trajectoires.

Carte SVG : équirectangulaire, emprise ajustée aux lieux publiés avec marge d’un degré. Coordonnées actuelles, nord en haut, aucune frontière ou fond cartographique tiers. Liste numérotée équivalente, points liés aux détails. Pas de géocodage, GPS ou transmission à un fournisseur. La projection est schématique, pas une carte scientifique pour mesurer des distances.

## Internationalisation future

La configuration centralise `name`, `tagline`, `description`, `language`, `futureLanguages`, `baseUrl`. `lang=fr`, français comme édition principale ; « EN à venir » n’est pas un faux lien. Les gabarits sont regroupés dans le générateur mais les libellés restent français. Avant une vraie édition anglaise : extraire les messages dans `locales/fr.json` et `locales/en.json`, définir des champs de traduction ou corpus par langue, routes `/en/`, alternates hreflang et politique de relecture **par langue**. Aucune traduction automatique non validée ne doit remplacer un champ manquant. C’est une préparation d’évolution, pas un moteur i18n complet déjà livré.

## Limites et maintenance

Une centaine de fiches convient au rendu et filtre côté client. Au-delà de quelques milliers : pagination, budgets index et tests de charge à reconsidérer. Pas de CMS, API d’édition ou multiutilisateur. Le champ reviewed est une déclaration éditoriale, pas une preuve cryptographique de validation humaine. Les sources peuvent devenir inaccessibles ; leur vérification et conservation relèvent du processus documentaire.
