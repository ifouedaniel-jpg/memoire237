"""Générateur HTML statique : validation stricte, publication fermée par défaut."""
import argparse
from datetime import date
from html import escape
import json
import math
from pathlib import Path
import re
import shutil
import tempfile
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
COLLECTIONS = ('events', 'people', 'places', 'themes', 'journeys')
ROUTES = dict(events='evenements', people='personnalites', places='lieux', themes='themes', journeys='parcours')
LABELS = dict(events='Événements', people='Personnalités', places='Lieux', themes='Thèmes', journeys='Parcours')
PERIODS = {'pre-1472': 'Avant 1472', '1472-1883': '1472–1883', '1884-1916': '1884–1916', '1916-1945': '1916–1945', '1945-1960': '1945–1960', '1960-1972': '1960–1972', '1972-1982': '1972–1982', '1982-2000': '1982–2000', '2000-now': 'Depuis 2000'}
RELATIONS = dict(sourceIds='sources', themeIds='themes', eventIds='events', personIds='people', placeIds='places')
E = lambda value: escape(str(value), quote=True)


def text(value):
    if isinstance(value, list):
        return '\n\n'.join(str(x) for x in value)
    return str(value) if value is not None else ''


CITATION = re.compile(r'\[([0-9]+)\]')
CITED_FIELDS = ('summary', 'body', 'context', 'consequences', 'significance', 'certainty', 'controversies')


def source_anchor(source):
    number = source.get('citationNumber')
    return f'source-{number}' if number is not None else 'source-id-' + source['id'].encode('utf-8').hex()


def inline(value, sources=()):
    """Escape all corpus text; only explicitly mapped citations become links."""
    mapping = {s['citationNumber']: s for s in sources if 'citationNumber' in s}
    raw = text(value)
    parts, end = [], 0
    for match in CITATION.finditer(raw):
        parts.append(E(raw[end:match.start()]))
        source = mapping.get(int(match[1]))
        label = E(match[0])
        parts.append(f'<a class="citation" href="#{source_anchor(source)}">{label}</a>' if source else label)
        end = match.end()
    return ''.join(parts) + E(raw[end:])


def paragraphs(value, sources=()):
    return ''.join('<p>' + inline(p, sources) + '</p>' for p in text(value).split('\n\n') if p.strip())


def published(item):
    return item.get('status') == 'publie' and item.get('reviewed') is True


def collective(item):
    return any(re.search(r'\b(?:collectifs?|collectives?)\b', str(item.get(k, '')).casefold()) for k in ('category', 'entryType'))


def partial_portrait(item):
    # Preserve the editorial declaration; do not infer completeness from length.
    return not collective(item) and 'portrait partiel' in text(item.get('editorialNote')).casefold()


def validate(data, root):
    def require(condition, message):
        if not condition:
            raise ValueError(message)
    require(isinstance(data, dict) and data.get('schemaVersion') == 1, 'schemaVersion doit valoir 1')
    index = {}
    citation_numbers = set()
    for group in ('sources',) + COLLECTIONS:
        rows = data.get(group, [])
        require(isinstance(rows, list), f'{group}: tableau requis')
        index[group] = {}
        slugs = set()
        for row in rows:
            require(isinstance(row, dict), f'{group}: objet requis')
            ident = row.get('id')
            require(isinstance(ident, str) and ident.strip() and ident not in index[group], f'{group}: ID absent ou doublon {ident}')
            index[group][ident] = row
            require(isinstance(row.get('title'), str) and row['title'].strip(), f'{ident}: titre requis')
            if group == 'sources':
                require(urlparse(row.get('url', '')).scheme in ('https', 'http') and bool(urlparse(row.get('url', '')).netloc), f'{ident}: URL source invalide')
                if 'citationNumber' in row:
                    number = row['citationNumber']
                    require(type(number) is int and number > 0 and number not in citation_numbers, f'{ident}: citationNumber doit être un entier positif unique')
                    citation_numbers.add(number)
                continue
            slug = row.get('slug', '')
            require(isinstance(slug, str) and re.fullmatch(r'[a-z0-9]+(?:-[a-z0-9]+)*', slug) and slug not in slugs, f'{ident}: slug invalide ou doublon')
            slugs.add(slug)
            require(row.get('status') in ('brouillon', 'a-verifier', 'valide', 'publie'), f'{ident}: statut invalide')
            require(isinstance(row.get('reviewed', False), bool), f'{ident}: reviewed doit être booléen')
            if published(row):
                require(bool(row.get('sourceIds')) and bool(text(row.get('summary')).strip()) and bool(text(row.get('body')).strip()), f'{ident}: publication sans sources/texte')
            if group == 'events':
                d = row.get('date', {})
                require(isinstance(d, dict) and type(d.get('startYear')) is int, f'{ident}: startYear entier requis')
                require(type(d.get('endYear', d['startYear'])) is int and d.get('endYear', d['startYear']) >= d['startYear'], f'{ident}: plage de dates invalide')
                require(d.get('precision') in ('year', 'day', 'range', 'circa', 'century') and bool(d.get('label')), f'{ident}: précision/libellé date requis')
                require(row.get('periodId') in PERIODS, f'{ident}: période inconnue')
                if d.get('iso'):
                    try:
                        date.fromisoformat(d['iso'])
                    except (ValueError, TypeError):
                        raise ValueError(f'{ident}: ISO invalide') from None
            if group == 'places':
                require(row.get('modernMap') is True, f'{ident}: modernMap:true requis')
                require(all(type(row.get(k)) in (int, float) and math.isfinite(row[k]) and abs(row[k]) <= bound for k, bound in [('lat', 90), ('lon', 180)]), f'{ident}: coordonnées invalides')
    for group in COLLECTIONS:
        for row in data.get(group, []):
            for field, target in RELATIONS.items():
                ids = row.get(field, [])
                require(isinstance(ids, list) and all(isinstance(i, str) and i in index[target] for i in ids), f'{row["id"]}: référence {field} invalide')
                if field == 'sourceIds':
                    require(len(ids) == len(set(ids)), f'{row["id"]}: sourceIds contient des doublons')
            if group == 'journeys':
                steps = row.get('steps', [])
                require(isinstance(steps, list), f'{row["id"]}: steps doit être un tableau')
                for step in steps:
                    require(isinstance(step, dict) and step.get('type') in ('event', 'person'), f'{row["id"]}: type étape invalide')
                    target = 'events' if step['type'] == 'event' else 'people'
                    require(step.get('id') in index[target], f'{row["id"]}: étape inconnue')
            if published(row):
                allowed = {index['sources'][sid]['citationNumber'] for sid in row['sourceIds'] if 'citationNumber' in index['sources'][sid]}
                for field in CITED_FIELDS:
                    for match in CITATION.finditer(text(row.get(field))):
                        require(int(match[1]) in allowed, f'{row["id"]}: citation [{match[1]}] sans source correspondante dans sourceIds ({field})')
                for sid in row['sourceIds']:
                    source = index['sources'][sid]
                    proof = source.get('evidenceFile', '')
                    path = (root / proof).resolve()
                    require(bool(proof) and path.is_relative_to(root.resolve()) and path.is_file(), f'{sid}: preuve absente ou hors projet')
                    require(bool(source.get('publisher')), f'{sid}: éditeur requis')
                    try:
                        date.fromisoformat(source.get('accessedAt', ''))
                    except (ValueError, TypeError):
                        raise ValueError(f'{sid}: accessedAt doit être une date ISO') from None
    return index


def href(group, item):
    return '/' + ROUTES[group] + '/' + item['slug'] + '/'


def card(group, item, attributes=''):
    date_label = item.get('date', {}).get('label', item.get('category', LABELS[group]))
    if group == 'people' and collective(item):
        date_label = 'Fiche collective'
    elif group == 'people' and partial_portrait(item):
        date_label = 'Portrait partiel'
    monogram = ''.join(w[0] for w in item['title'].split()[:2])
    return f'<article class="card" {attributes}><div class="card-mark" aria-hidden="true">{E(monogram)}</div><div class="card-content"><span class="eyebrow">{E(date_label)}</span><h2><a href="{href(group, item)}">{E(item["title"])}</a></h2><p>{E(item.get("summary", ""))}</p><span class="card-note">{E(LABELS[group])} · Lire la fiche →</span></div></article>'


def build(data, output, root=ROOT, base_url=None):
    index = validate(data, root)
    cfg = json.loads((root / 'site_config.json').read_text())
    if base_url is not None:
        cfg['baseUrl'] = base_url.rstrip('/')
    parsed_base = urlparse(cfg['baseUrl'])
    if parsed_base.scheme not in ('http', 'https') or not parsed_base.netloc or parsed_base.query or parsed_base.fragment:
        raise ValueError('baseUrl doit être une URL HTTP(S) sans query ni fragment')
    prefix = parsed_base.path.rstrip('/')

    def public_url(route):
        return prefix + route
    public = {k: [x for x in data.get(k, []) if published(x)] for k in COLLECTIONS}
    public['journeys'] = [j for j in public['journeys'] if all(published(index['events' if s['type'] == 'event' else 'people'][s['id']]) for s in j.get('steps', []))]
    public['events'].sort(key=lambda e: (e['date']['startYear'], e['title']))
    for group in ('people', 'themes', 'places'):
        public[group].sort(key=lambda x: x['title'].casefold())
    public_ids = {k: {x['id'] for x in rows} for k, rows in public.items()}
    used_sources = {sid for rows in public.values() for row in rows for sid in row.get('sourceIds', [])}
    sources = [s for s in data.get('sources', []) if s['id'] in used_sources]
    output.mkdir(parents=True, exist_ok=True)
    paths = []
    nav = [('/', 'Accueil'), ('/frise/', 'Frise'), ('/personnalites/', 'Personnalités'), ('/themes/', 'Thèmes'), ('/lieux/', 'Lieux'), ('/parcours/', 'Parcours'), ('/recherche/', 'Recherche')]

    def page(route, title, description, body, detail=False):
        path = output / route.strip('/') / 'index.html'
        path.parent.mkdir(parents=True, exist_ok=True)
        canonical = cfg['baseUrl'].rstrip('/') + route
        structured = {'@context': 'https://schema.org', '@type': 'Article' if detail else 'WebPage', 'name': title, 'description': description, 'inLanguage': cfg['language'], 'url': canonical, 'isPartOf': {'@type': 'WebSite', 'name': cfg['name']}}
        ld = json.dumps(structured, ensure_ascii=False).replace('<', '\\u003c')
        navigation = ''.join(f'<a href="{url}"' + (' aria-current="page"' if url == route else '') + f'>{E(label)}</a>' for url, label in nav)
        html = f'''<!doctype html><html lang="{E(cfg['language'])}"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{E(title)} — {E(cfg['name'])}</title><meta name="description" content="{E(description)}"><meta name="theme-color" content="#174b3c"><link rel="canonical" href="{E(canonical)}"><meta property="og:title" content="{E(title)} — {E(cfg['name'])}"><meta property="og:description" content="{E(description)}"><meta property="og:type" content="{'article' if detail else 'website'}"><meta property="og:url" content="{E(canonical)}"><link rel="icon" href="/assets/icon.svg" type="image/svg+xml"><link rel="stylesheet" href="/assets/style.css"><script defer src="/assets/app.js"></script><script type="application/ld+json">{ld}</script></head><body><a class="skip" href="#contenu">Aller au contenu</a><header class="site-header"><div class="header-inner"><a class="brand" href="/"><span class="brand-symbol" aria-hidden="true">M<span>237</span></span><span>{E(cfg['name'])}<small>Musée numérique · Cameroun</small></span></a><span class="language" lang="fr">FR <span aria-hidden="true">/</span> <span title="Version anglaise à venir">EN à venir</span></span></div><nav aria-label="Navigation principale">{navigation}</nav></header><main id="contenu" tabindex="-1">{body}</main><footer><div><strong>{E(cfg['name'])}</strong><p>{E(cfg['tagline'])}</p></div><nav aria-label="Informations"><a href="/sources/">Sources &amp; méthode</a><a href="/a-propos/">À propos</a><a href="/recherche/">Rechercher</a></nav><p class="fine">Édition documentaire en construction. Aucune image d’archive ou portrait sans droits établis. Les monogrammes sont des repères typographiques, pas des portraits.</p></footer></body></html>'''
        if base_url is not None:
            html = html.replace('Édition locale partielle', 'Édition documentaire partielle')
            html = html.replace('Limites de cette édition locale', 'Limites de cette édition partielle')
            html = html.replace('Pas de déploiement public, pas de compte utilisateur, pas de commentaires et pas de suivi publicitaire. La validation historique et la politique éditoriale doivent être confirmées avant toute ouverture.', 'Édition documentaire partielle consultable publiquement, sans compte utilisateur, commentaires ni suivi publicitaire. La validation historienne reste à réaliser ; les limites et lacunes sont explicites.')
        # Rebase generated local attributes only; preserve external URLs and citations.
        html = re.sub(r'\b(href|src)="(/(?!/)[^\"]*)"', lambda m: m[1] + '="' + E(prefix) + m[2] + '"', html)
        path.write_text(html, encoding='utf-8')
        paths.append(route)

    empty = '<div class="empty"><span class="eyebrow">Le temps de la vérification</span><h2>Les premières fiches se préparent.</h2><p>Aucune fiche répondant aux critères de publication n’est disponible ici. Nous préférons une place vide à un récit non vérifié.</p><a href="/sources/">Comprendre notre méthode →</a></div>'
    counts = ''.join(f'<li><strong>{len(public[k]):02d}</strong><span>{E(LABELS[k])}</span></li>' for k in COLLECTIONS)
    corpus_notice = ''
    if any(public.values()):
        partials = sum(partial_portrait(p) for p in public['people'])
        collectives = sum(collective(p) for p in public['people'])
        gaps = '1972–1982 : aucune fiche publiée dans cette édition.' if not any(e['periodId'] == '1972-1982' for e in public['events']) else ''
        corpus_notice = f'<section class="reading corpus-notice"><h2>Corpus incomplet</h2><p>Édition locale partielle : les objectifs éditoriaux ne sont pas tous atteints. {partials} portrait(s) partiel(s) et {collectives} fiche(s) collective(s) ; ces collectifs ne sont pas des biographies individuelles. Relecture documentaire par des agents, sans validation historienne.</p><p>{gaps} Une lacune documentaire ne signifie pas une absence d’histoire.</p></section>'
    featured = [x for x in public['events'] if x.get('featured')] or public['events']
    home_cards = ''.join(card('events', x) for x in featured[:3]) or empty
    intro = f'''<section class="hero"><div class="hero-copy"><p class="eyebrow">Des trajectoires, des voix, des mémoires</p><h1>Une histoire à lire.<br><em>Des mémoires<br>à explorer.</em></h1><p class="lead">{E(cfg['description'])}</p><div class="actions"><a class="button" href="/frise/">Explorer la frise <span aria-hidden="true">↗</span></a><a class="text-link" href="/parcours/">Suivre un parcours →</a></div><p class="fine">Des repères documentés. Des incertitudes explicites.</p></div><div class="hero-art" aria-hidden="true"><span class="art-label">ARCHIVES / TRANSMISSIONS</span><div class="art-ring ring-one"></div><div class="art-ring ring-two"></div><span class="art-number">237</span><div class="art-caption">Relier les époques.<br>Éclairer les perspectives.</div><span class="art-dash"></span></div></section><section class="stats" aria-label="Fiches actuellement publiées"><ul>{counts}</ul><p>Fiches sourcées et relues · compteurs réels</p></section><section class="section"><div class="section-heading"><div><p class="eyebrow">Entrer dans l’histoire</p><h2>Des repères pour commencer</h2></div><a href="/frise/">Toute la frise →</a></div><div class="grid">{home_cards}</div></section><section class="editorial-band"><span class="section-number">01 / NOTRE ENGAGEMENT</span><div><h2>Raconter sans simplifier.<br>Documenter sans figer.</h2><p>Une date peut être approximative. Une interprétation peut être discutée. Chaque fiche distingue les repères, le contexte et les questions ouvertes — et vous donne accès à ses sources.</p><a href="/sources/">Lire notre méthode →</a></div></section><section class="section"><p class="eyebrow">Choisir son entrée</p><h2>Une mémoire, plusieurs chemins.</h2><div class="entry-grid"><a href="/personnalites/"><span>01</span><h3>Des vies et des voix</h3><p>Découvrir les personnalités et leurs trajectoires.</p>Personnalités →</a><a href="/lieux/"><span>02</span><h3>Des lieux de mémoire</h3><p>Situer les récits, sans confondre les frontières et les époques.</p>Lieux →</a><a href="/themes/"><span>03</span><h3>Des fils à suivre</h3><p>Relier les événements au-delà de leur chronologie.</p>Thèmes →</a></div></section>'''
    intro = intro.replace('<section class="section">', corpus_notice + '<section class="section">', 1)
    page('/', 'Accueil', cfg['description'], intro)

    def heading(kicker, title, desc, sources=()):
        return f'<section class="page-heading"><p class="eyebrow">{E(kicker)}</p><h1>{E(title)}</h1><p class="lead">{inline(desc, sources)}</p></section>'

    for group in COLLECTIONS:
        route = '/frise/' if group == 'events' else '/' + ROUTES[group] + '/'
        descriptions = dict(events='Traverser les périodes, croiser les récits. Les dates approximatives restent signalées.', people='Des trajectoires individuelles et, lorsque signalés, des collectifs à replacer dans leurs contextes. Les fiches collectives ne sont pas des biographies individuelles.', themes='Explorer les liens entre les événements, les personnes et les lieux.', places='Repères géographiques actuels : cette carte ne représente aucune frontière historique.', journeys='Des étapes choisies pour lire ensemble les événements et les trajectoires.')
        body = heading('Explorer / ' + LABELS[group], 'La frise chronologique' if group == 'events' else LABELS[group], descriptions[group])
        if group in ('events', 'people'):
            categories = sorted({str(x.get('category', 'Non classé')) for x in public[group]})
            options = ''.join(f'<option value="{E(c)}">{E(c)}</option>' for c in categories)
            body += '<form class="filters" data-filters><div><label for="category">Catégorie</label><select id="category" name="category"><option value="">Toutes les catégories</option>' + options + '</select></div>'
            if group == 'events':
                periods = ''.join(f'<option value="{k}">{v}</option>' for k, v in PERIODS.items())
                body += f'<div><label for="period">Période</label><select id="period" name="period"><option value="">Toutes les périodes</option>{periods}</select></div><div><label for="year">Année</label><input id="year" name="year" type="number" step="1" placeholder="Toutes les années" aria-describedby="year-help"><small id="year-help">Vide = toutes les années ; inclut les plages de dates.</small></div>'
            body += '<button class="button" type="submit">Filtrer</button><button class="secondary" type="reset">Réinitialiser</button></form><noscript><p>Sans JavaScript, toutes les fiches sont affichées. Les filtres et la recherche interactive nécessitent JavaScript.</p></noscript><p data-result-count role="status" aria-live="polite"></p><div class="empty" data-filter-empty hidden>Aucune fiche pour ces critères. Une année sans document publié ne signifie pas une absence d’histoire. Essayez une autre année ou réinitialisez les filtres.</div>'
        if group == 'places':
            body += map_markup(public[group])
        cards = []
        for row in public[group]:
            attrs = ''
            if group in ('events', 'people'):
                d = row.get('date', {})
                attrs = f'data-filter-item data-category="{E(row.get("category", "Non classé"))}" data-period="{E(row.get("periodId", ""))}" data-start="{E(d.get("startYear", ""))}" data-end="{E(d.get("endYear", d.get("startYear", "")))}"'
            cards.append(card(group, row, attrs))
        body += '<section class="section grid" aria-label="Fiches">' + (''.join(cards) or empty) + '</section>'
        page(route, 'Frise chronologique' if group == 'events' else LABELS[group], descriptions[group], body)
        if group == 'events':
            page('/evenements/', 'Événements', descriptions[group], body)
        for row in public[group]:
            row_sources = [index['sources'][sid] for sid in row.get('sourceIds', [])]
            detail = f'<div class="breadcrumbs"><a href="/">Accueil</a> / <a href="{route}">{E(LABELS[group])}</a></div>'
            detail += heading(row.get('date', {}).get('label', row.get('category', LABELS[group])), row['title'], row.get('summary', ''), row_sources)
            detail += '<div class="detail-layout"><article class="reading"><p class="verified">Fiche publiée · relecture documentaire déclarée par des agents, sans validation historienne</p>' + paragraphs(row.get('body'), row_sources)
            fields = [('context', 'Contexte'), ('consequences', 'Conséquences'), ('significance', 'Rôle et portée'), ('certainty', 'Degré de certitude'), ('controversies', 'Questions ouvertes et controverses'), ('editorialNote', 'Note éditoriale')]
            for field, label in fields:
                value = row.get(field)
                if value:
                    detail += f'<section><h2>{label}</h2>{paragraphs(value, row_sources)}</section>'
            if group == 'people':
                if partial_portrait(row):
                    detail += '<p class="fine">Portrait partiel : ce texte ne constitue pas une biographie complète.</p>'
                detail += '<p class="fine">Repère typographique : aucun portrait historique n’est représenté.</p>'
                if collective(row):
                    detail += '<p class="fine">Fiche collective : cette entrée décrit un groupe, pas une biographie individuelle.</p>'
                for field, label in ([] if collective(row) else [('birthYear', 'Naissance'), ('deathYear', 'Décès')]):
                    if row.get(field) is not None:
                        detail += f'<p>{label} : {E(row[field])}</p>'
            if group == 'places':
                detail += map_markup([row]) + f'<p>Coordonnées actuelles : {E(row["lat"])}°, {E(row["lon"])}°. Aucun tracé de frontière historique.</p>'
            if group == 'journeys':
                detail += '<h2>Les étapes du parcours</h2>'
                if row.get('durationMinutes'):
                    detail += f'<p>Durée indicative : {E(row["durationMinutes"])} minutes.</p>'
                detail += '<ol class="steps">'
                for step in row.get('steps', []):
                    target = 'events' if step['type'] == 'event' else 'people'
                    item = index[target][step['id']]
                    detail += f'<li><a href="{href(target, item)}">{E(item["title"])}</a><p>{E(item.get("summary", ""))}</p></li>'
                detail += '</ol>'
            detail += '</article><aside class="related"><h2>Relier les mémoires</h2>'
            related_count = 0
            for field, target in RELATIONS.items():
                if target == 'sources':
                    continue
                ids = set(row.get(field, []))
                # Relations inverses : rend les thèmes/lieux réellement explorables.
                reverse_field = {'events':'eventIds','people':'personIds','places':'placeIds','themes':'themeIds','journeys':None}[group]
                for candidate in public[target]:
                    if candidate['id'] in ids or (reverse_field and row['id'] in candidate.get(reverse_field, [])):
                        if target == group and candidate['id'] == row['id']:
                            continue
                        detail += f'<p><span class="eyebrow">{E(LABELS[target])}</span><br><a href="{href(target, candidate)}">{E(candidate["title"])}</a></p>'
                        related_count += 1
            if not related_count:
                detail += '<p>Aucune relation publiée pour le moment.</p>'
            detail += '</aside></div><section class="source-box"><h2>Sources de cette fiche</h2><p>Les sources sont des points d’appui, pas une garantie d’absence de débat. Les preuves locales sont conservées par la rédaction.</p><ul>'
            for sid in row.get('sourceIds', []):
                s = index['sources'][sid]
                number = f'<span class="citation-number">[{s["citationNumber"]}]</span> ' if 'citationNumber' in s else ''
                detail += f'<li id="{source_anchor(s)}">{number}<a href="{E(s["url"])}" rel="noopener noreferrer">{E(s["title"])}</a> — {E(s.get("publisher", ""))} · consulté le {E(s.get("accessedAt", ""))}</li>'
            detail += '</ul><a href="/sources/">Notre protocole de vérification →</a></section>'
            page(href(group, row), row['title'], row.get('summary', ''), detail, True)

    search = heading('Trouver un repère', 'Rechercher dans les mémoires', 'Une recherche transversale, insensible aux accents et à la casse, dans les seules fiches publiées et relues.')
    search += '<form class="search-form" data-search role="search"><label for="q">Mot, nom, lieu ou sujet</label><div><input id="q" name="q" type="search" placeholder="Que souhaitez-vous explorer ?" autocomplete="off"><button class="button" type="submit">Rechercher</button></div></form><p data-search-status role="status" aria-live="polite">Saisissez un mot pour explorer les fiches.</p><section class="grid" data-search-results aria-label="Résultats de recherche"></section><noscript><p>La recherche nécessite JavaScript. Retrouvez toutes les fiches par les <a href="/frise/">répertoires</a>.</p></noscript>'
    page('/recherche/', 'Recherche', 'Recherche globale dans les fiches publiées.', search)
    source_list = ''
    for s in sources:
        number = f'<span class="citation-number">[{s["citationNumber"]}]</span> ' if 'citationNumber' in s else ''
        source_list += f'<li id="{source_anchor(s)}"><h2>{number}<a href="{E(s["url"])}" rel="noopener noreferrer">{E(s["title"])}</a></h2><p>{E(s.get("publisher", ""))} · consulté le {E(s.get("accessedAt", ""))}</p></li>'
    methodology = heading('Transparence documentaire', 'Sources & méthode', 'Rendre visible ce que nous savons, ce qui reste discuté et les documents qui étayent chaque récit.') + '''<article class="reading method"><h2>Une publication, pas une certitude absolue</h2><p>Les contenus suivent quatre états : brouillon, à vérifier, validé, publié. Seules les fiches explicitement publiées et marquées comme relues sont accessibles. Cette édition repose sur une relecture documentaire par des agents : ce n’est pas une validation historienne. Le logiciel contrôle une déclaration éditoriale, pas la qualité du travail ni une certification par un comité d’historiens. Les éventuelles dates de relecture indiquent ce contrôle documentaire par des agents, pas une expertise historienne. Les dates de consultation des sources indiquent leur accès documentaire, et ne sont ni des dates de relecture ni une validation de leur contenu.</p><h2>Des sources attachées aux récits</h2><p>Chaque fiche publique cite ses références, leur éditeur et leur date de consultation. Une preuve documentaire locale doit exister avant publication. Les références invalides bloquent la construction du site. Une source unique ne suffit pas toujours : les sujets sensibles demandent un croisement critique et un examen historiographique.</p><h2>Dates, contexte et controverses</h2><p>Une date approximative conserve son libellé. Une plage de dates n’est pas ramenée à un jour fictif. Le filtre par année inclut les événements dont la plage couvre cette année. Le contexte, les conséquences et les controverses sont distingués quand le corpus les documente. L’absence de rubrique n’implique pas l’absence de débat.</p><h2>Carte : des coordonnées, pas des frontières</h2><p>La carte est un schéma longitude/latitude de lieux dans la géographie actuelle. Elle n’affirme aucune continuité de frontières ou de souveraineté. Les positions et noms demandent leur propre contextualisation historique.</p><h2>Images et droits</h2><p>Aucun portrait ni photographie d’archive n’est utilisé à ce stade. Les initiales et compositions graphiques sont des substituts typographiques explicites, sans prétention de ressemblance. Tout futur média devra être accompagné de sa licence, de son attribution et d’une preuve de droits.</p><h2>Corrections et pluralité</h2><p>Ce MVP ne collecte aucune contribution ou donnée personnelle. Le circuit public de signalement reste à définir avant ouverture. La pluralité des récits n’autorise ni l’équivalence automatique des sources, ni l’effacement de leurs biais.</p></article><section class="section"><h2>Bibliographie des fiches publiques</h2>''' + ('<ul class="bibliography">' + source_list + '</ul>' if source_list else '<p>Aucune source n’est encore associée à une fiche publiée. La collecte documentaire se poursuit.</p>') + '</section>'
    methodology = methodology.replace('<article class="reading method">', corpus_notice + '<article class="reading method">', 1)
    page('/sources/', 'Sources et méthodologie', 'Critères de publication, limites et bibliographie des fiches.', methodology)
    about = heading('Le projet', 'Une mémoire en partage', cfg['tagline']) + '<article class="reading method"><h2>Un musée numérique, en construction</h2><p>Ce projet propose des entrées chronologiques, biographiques, thématiques et géographiques dans l’histoire du Cameroun. Il s’adresse au public curieux, aux élèves et aux personnes qui souhaitent retrouver le chemin des sources.</p><h2>Fiabilité avant quantité</h2><p>Les objectifs éditoriaux sont 50 événements, 30 biographies, 8 thèmes, 20 lieux et un parcours. Ce sont des objectifs, pas des compteurs préremplis. Une fiche absente ou en relecture ne paraît pas sur le site.</p><h2>Accessibilité et sobriété</h2><p>Navigation au clavier, texte redimensionnable, contrastes lisibles, pages légères sans police distante ni traceur. La version française est la première édition ; l’architecture prévoit une future traduction anglaise, qui n’est pas encore disponible.</p><h2>Limites de cette édition locale</h2><p>Pas de déploiement public, pas de compte utilisateur, pas de commentaires et pas de suivi publicitaire. La validation historique et la politique éditoriale doivent être confirmées avant toute ouverture.</p><a href="/sources/">Consulter les règles documentaires →</a></article>'
    page('/a-propos/', 'À propos', 'Intentions et limites du musée numérique.', about)
    page('/404/', 'Page introuvable', 'Cette page n’existe pas ou n’est pas publiée.', heading('Erreur 404', 'Ce repère n’est pas disponible.', 'La fiche peut être absente ou encore en relecture.') + '<a class="button" href="/">Retour à l’accueil</a>')
    search_rows = []
    for group, rows in public.items():
        for row in rows:
            search_rows.append(dict(title=row['title'], summary=row.get('summary', ''), text=' '.join(text(row.get(k, '')) for k in ('title', 'summary', 'body', 'context', 'consequences', 'significance', 'controversies')), url=public_url(href(group, row)), type=LABELS[group]))
    (output / 'search-index.json').write_text(json.dumps(search_rows, ensure_ascii=False), encoding='utf-8')
    sitemap = '<?xml version="1.0" encoding="UTF-8"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">' + ''.join('<url><loc>' + E(cfg['baseUrl'].rstrip('/') + p) + '</loc></url>' for p in paths if p != '/404/') + '</urlset>'
    (output / 'sitemap.xml').write_text(sitemap, encoding='utf-8')
    (output / 'robots.txt').write_text('User-agent: *\nDisallow: /\n# Édition locale : pas d’indexation avant validation publique.\n', encoding='utf-8')
    if (root / 'assets').exists():
        (output / 'assets').mkdir(exist_ok=True)
        for name in ('style.css', 'app.js', 'icon.svg'):
            source = root / 'assets' / name
            if source.is_symlink() or not source.resolve().is_relative_to(root.resolve()):
                raise ValueError('Asset hors projet ou lien symbolique refusé')
            shutil.copyfile(source, output / 'assets' / name)
    shutil.copyfile(output / '404/index.html', output / '404.html')
    (output / '.nojekyll').write_text('', encoding='utf-8')
    report = dict(publicCounts={k:len(v) for k,v in public.items()}, sources=len(sources), pages=len(paths), corpusPresent=(root / 'research/corpus.json').exists())
    (output / 'build-report.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    return report


def map_markup(rows):
    # Projection équirectangulaire schématique, aucune frontière.
    if not rows:
        return '<section class="map-panel"><h2>Carte des lieux</h2><p>Le schéma accueillera les lieux publiés avec leurs coordonnées actuelles. Aucun point fictif n’est affiché.</p></section>'
    west = min(x['lon'] for x in rows) - 1
    east = max(x['lon'] for x in rows) + 1
    south = min(x['lat'] for x in rows) - 1
    north = max(x['lat'] for x in rows) + 1
    dots = ''
    for i, row in enumerate(rows, 1):
        x = 55 + 690 * (row['lon'] - west) / (east - west)
        y = 40 + 320 * (north - row['lat']) / (north - south)
        dots += f'<a href="{href("places", row)}" aria-label="{i} — {E(row["title"])}"><circle cx="{x:.2f}" cy="{y:.2f}" r="10"/><text x="{x:.2f}" y="{y-16:.2f}" text-anchor="middle">{i}</text></a>'
    listing = ''.join(f'<li><a href="{href("places", r)}">{E(r["title"])}</a> — {E(r["lat"])}° N, {E(r["lon"])}° E</li>' for r in rows)
    return f'<section class="map-panel"><h2>Repères géographiques actuels</h2><p>Schéma géolocalisé sans frontières, projection équirectangulaire. Nord en haut ; positions relatives, pas une carte de souveraineté. Les numéros renvoient à la liste accessible.</p><svg class="map" viewBox="0 0 800 410" role="group" aria-label="Schéma longitude et latitude des lieux"><path class="map-grid" d="M55 40H745V360H55Z M55 120H745 M55 200H745 M55 280H745 M227 40V360 M400 40V360 M572 40V360"/>{dots}<text x="55" y="390">{west:.1f}° E</text><text x="680" y="390">{east:.1f}° E</text><text x="16" y="30">N ↑</text></svg><ol>{listing}</ol></section>'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=ROOT / 'dist', help='Sécurité : uniquement dist/ de ce projet')
    parser.add_argument('--base-url', help='URL canonique, avec sous-chemin éventuel ; configuration locale inchangée')
    args = parser.parse_args()
    corpus = ROOT / 'research/corpus.json'
    if corpus.exists():
        data = json.loads(corpus.read_text(encoding='utf-8'))
    else:
        print('Corpus absent : édition vide, sans faits historiques inventés.')
        data = dict(schemaVersion=1, sources=[], **{k:[] for k in COLLECTIONS})
    target = args.output.resolve()
    if target != ROOT / 'dist' or args.output.is_symlink():
        raise ValueError('Sortie autorisée uniquement dans dist/ du projet, sans lien symbolique')
    target.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='.build-', dir=target.parent) as tmp:
        report = build(data, Path(tmp), ROOT, base_url=args.base_url)
        if target.exists():
            if not (target / 'build-report.json').is_file():
                raise ValueError('Refus d’écraser un dossier sans marqueur build-report.json')
            shutil.rmtree(target)
        Path(tmp).rename(target)
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
