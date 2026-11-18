# Modèle de contenu

Référence contractuelle : [docs/CONTENT_CONTRACT.md](docs/CONTENT_CONTRACT.md). Seul fichier d’entrée applicatif : `research/corpus.json`, créé/accepté par Master. Le candidat reste privé et ignoré.

## Schéma v1

| Collection | Champs spécifiques |
|---|---|
| sources | id, title, url HTTP(S), publisher, accessedAt ISO YYYY-MM-DD, evidenceFile relatif au projet |
| events | date {startYear, endYear?, label, precision, iso?}, periodId ; category, featured, context, consequences, certainty, controversies facultatifs |
| people | category, birthYear?, deathYear?, significance, controversies facultatifs |
| places | lat, lon, modernMap:true obligatoires |
| themes | champs communs |
| journeys | steps [{type:event\|person,id}], durationMinutes facultatif |

Racine : schemaVersion entier 1 et tableaux sources/events/people/places/themes/journeys. Les collections omises sont traitées comme vides ; le format contractuel recommandé inclut tous les tableaux.

Commun : id, slug, title, summary, body, status, reviewed, sourceIds, themeIds, eventIds, personIds, placeIds. IDs uniques **par collection**, slugs uniques par collection. Slug ASCII minuscules/chiffres séparés par tirets. Les champs relationnels absents = [] ; les autres champs optionnels absents ne bloquent pas le rendu. body accepte texte ou tableau de paragraphes texte. Les champs inconnus sont tolérés, non exposés automatiquement.

## Validation et publication

- Toutes les références sont résolues avant filtrage ; inconnue = échec du build.
- Statuts acceptés : brouillon, a-verifier, valide, publie. reviewed booléen strict, défaut false.
- Public : uniquement publie + reviewed true + titre/résumé/corps non vides + sourceIds non vide.
- Chaque source utilisée par une fiche publique doit avoir éditeur, date de consultation valide, preuve locale existante **dans** le projet, URL HTTP(S). Le fichier de preuve peut être sous research/ ; il n’est jamais rendu ou copié.
- Un parcours qui pointe vers un événement/personnage non public n’a ni page, ni entrée dans la recherche ou le sitemap. La référence elle-même est valide, l’expérience ne l’est pas encore.
- Les relations valides vers le privé sont omises du rendu. La bibliographie globale inclut seulement les sources réellement utilisées par des fiches publiques.
- Le logiciel ne peut pas décider si une assertion est historiquement fondée. L’accord Master et l’audit documentaire restent indispensables avant de déclarer la livraison du corpus.

## Dates

precision : year, day, range, circa, century. startYear entier, endYear entier >= début. label obligatoire ; iso facultatif, validé comme date ISO lorsqu’il est fourni. Aucun jour précis n’est déduit d’une année. Filtre année : début <= année <= fin, ou année = début si fin absente. Pour un siècle ou une approximation, renseigner les bornes documentaires si elles sont connues ; le logiciel ne calcule pas une plage implicite arbitraire.

periodId : pre-1472, 1472-1883, 1884-1916, 1916-1945, 1945-1960, 1960-1972, 1972-1982, 1982-2000, 2000-now. Le champ est éditorial : le code vérifie la valeur, pas l’interprétation des bornes ni la cohérence historique.

## Médias et sécurité

Aucun champ média ingéré au MVP. Monogrammes et visuel géométrique créés pour l’interface ; ne représentent pas des portraits ou archives. Les textes sont échappés en HTML ; liens documentaires limités à HTTP(S), relations locales générées depuis slugs validés. Les chemins de preuve ne sont ni des liens publics ni des métadonnées exposées. Les dossiers privés, sauvegardes, tests et code Python ne sont pas présents dans le build.

## Mesure des lacunes

`dist/build-report.json` compte les fiches réellement publiques par collection, les sources utilisées et les pages. Ce rapport interne est refusé par le serveur. Les compteurs de l’accueil sont calculés à partir des mêmes collections. Objectifs 50/30/8/20/1 non atteints tant qu’aucun corpus n’a été accepté ; aucun remplissage synthétique autorisé. En l’absence du corpus : zéro fiche, message de préparation et méthodologie disponibles.
