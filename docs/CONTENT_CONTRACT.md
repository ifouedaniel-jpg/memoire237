# Contrat documentaire — MÉMOIRE 237

Le développeur ne modifie jamais `research/`. Corpus attendu : `research/corpus.json`. En son absence, build vide honnête (aucune donnée historique de démonstration). Les fixtures fictives sont uniquement dans les tests.

Racine : `{schemaVersion:1,sources:[],events:[],people:[],places:[],themes:[],journeys:[]}`.
Source : `{id,title,url,publisher,accessedAt,evidenceFile}`. URL HTTP(S), preuve locale relative au projet. La preuve doit exister à la publication. `accessedAt` ISO date.
Commun fiches : `{id,slug,title,summary,body,status,reviewed,sourceIds,themeIds,eventIds,personIds,placeIds}`. `body` texte brut (ou liste de paragraphes texte), jamais HTML de confiance. Champs relationnels facultatifs = []. `reviewed` booléen strict, pas une date ou chaîne.
Statuts : `brouillon`, `a-verifier`, `valide`, `publie`. **Seul `status: "publie"` ET `reviewed: true` est public.** La vérification documentaire humaine reste nécessaire : le logiciel ne peut pas l'attester seul. Fiche publique : au moins une source, summary et body non vides.
Événement : `date:{startYear,endYear?,label,precision:year|day|range|circa|century,iso?}`, `periodId`, `category`, `featured`, `context`, `consequences`, `certainty`, `controversies`. Périodes : pre-1472,1472-1883,1884-1916,1916-1945,1945-1960,1960-1972,1972-1982,1982-2000,2000-now. Années entières ; l'année sert au tri et au filtre, le libellé d'origine est affiché sans précision artificielle.
Personne : `category,birthYear?,deathYear?,significance,controversies`. Lieu : `lat,lon,modernMap:true` (coordonnées actuelles explicitement). Thème : commun. Parcours : `steps:[{type:event|person,id}],durationMinutes`.

Toute référence invalide, même dans un brouillon, fait échouer le build. Les références valides vers une fiche non publique ne sont pas affichées. Un parcours contenant une étape non publique est lui-même retiré de la publication pour éviter une expérience tronquée. IDs uniques dans chaque collection ; slugs uniques dans leur collection, ASCII minuscules/chiffres/tirets, sans slash. Les médias ne sont pas ingérés : uniquement substituts typographiques honnêtes.

Métadonnées optionnelles additionnelles tolérées ; champs spécifiques optionnels absents ne cassent pas le rendu (hors date d'événement et coordonnées de lieu). Pas de minimum de quantité imposé au build : la fiabilité prime sur les objectifs 50/30/8/20/1. Configuration unique du site : `site_config.json`.
