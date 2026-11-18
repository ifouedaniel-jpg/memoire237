"""QA du corpus accepté uniquement, jamais du candidat ni de fixtures.

    python3 tests/qa_real_corpus.py

Utilise les outils existants dans .qa/, sans installation ni réseau externe.
Construit dans un répertoire éphémère .qa/ et sert sur un port loopback libre ;
ne touche ni dist/, ni le serveur de prévisualisation, ni research/.
Preuves : evidence/integration-real-corpus-*. Corpus absent = skipped, pas passed.
Les href externes sont inventoriés, pas téléchargés : leur qualité documentaire
et leur disponibilité distante restent hors de cette QA navigateur locale.
"""
import functools
import hashlib
from html.parser import HTMLParser
from http.server import ThreadingHTTPServer
import importlib.util
import json
import os
from pathlib import Path
import sys
import tempfile
import threading
import unicodedata
from urllib.parse import unquote, urlencode, urljoin, urlsplit

ROOT = Path(__file__).resolve().parents[1]


class HTMLScan(HTMLParser):
    def __init__(self, markup):
        super().__init__()
        self.ids, self.hrefs = [], []
        self.feed(markup)

    def handle_starttag(self, tag, attrs):
        for key, value in attrs:
            if key == 'id' and value is not None:
                self.ids.append(value)
            if key == 'href' and value is not None:
                self.hrefs.append(value)


def check_fragment(markup, fragment):
    target = unquote(fragment)
    count = HTMLScan(markup).ids.count(target)
    assert count == 1, f'ancre non unique ou absente : #{target} ({count} cibles)'


def normalize(value):
    return ''.join(c for c in unicodedata.normalize('NFD', value) if not unicodedata.combining(c)).lower().replace('œ', 'oe').replace('æ', 'ae')


def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def exercise_search(page, origin, search_rows):
    checks = []
    for query in ('reunification', 'réunification', 'RÉUNIFICATION', ''):
        expected = sorted(r['url'] for r in search_rows if query and all(t in normalize(r['text']) for t in normalize(query).split()))
        page.goto(origin + '/recherche/?' + urlencode({'q': query}))
        page.wait_for_function("""() => {const s=document.querySelector('[data-search-status]').textContent;
            return !s.includes('en cours') && (s.includes('résultat') || s.includes('Saisissez'));} """)
        actual = sorted(page.locator('[data-search-results] a').evaluate_all('(xs)=>xs.map(x=>x.getAttribute("href"))'))
        assert actual == expected, f'recherche {query!r}: {actual} != {expected}'
        checks.append(dict(query=query, results=len(actual)))
    return checks


def exercise_filters(page, origin, data, builder):
    checks = []
    for group, route in (('events', '/frise/'), ('people', '/personnalites/')):
        rows = [r for r in data.get(group, []) if builder.published(r)]
        cases = [dict(category='', period='', year='')]
        categories = sorted({str(r.get('category', 'Non classé')) for r in rows})
        cases += [dict(category=c, period='', year='') for c in categories]
        if group == 'events':
            cases += [dict(category='', period=p, year='') for p in builder.PERIODS]
            cases += [dict(category='', period='', year='1700')]
            cases += [dict(category=str(r.get('category', 'Non classé')), period=r['periodId'], year=str(r['date']['startYear'])) for r in rows]
        page.goto(origin + route)
        for selected in cases:
            page.locator('#category').select_option(selected['category'])
            if group == 'events':
                page.locator('#period').select_option(selected['period'])
                page.locator('#year').fill(selected['year'])
            page.get_by_role('button', name='Filtrer', exact=True).click()
            expected = []
            for row in rows:
                d = row.get('date', {})
                if selected['category'] and str(row.get('category', 'Non classé')) != selected['category']:
                    continue
                if selected['period'] and row.get('periodId') != selected['period']:
                    continue
                if selected['year'] and not d['startYear'] <= int(selected['year']) <= d.get('endYear', d['startYear']):
                    continue
                expected.append(builder.href(group, row))
            actual = sorted(page.locator('[data-filter-item]:visible h2 a').evaluate_all('(xs)=>xs.map(x=>x.getAttribute("href"))'))
            assert actual == sorted(expected), f'filtres {route} {selected}: {actual} != {expected}'
            assert page.locator('[data-filter-empty]').is_visible() == (not expected)
            shared_url = page.url
            page.reload()
            assert page.locator('[data-filter-item]:visible').count() == len(expected), shared_url
            checks.append(dict(route=route, selection=selected, results=len(actual)))
        page.get_by_role('button', name='Réinitialiser', exact=True).click()
        assert page.locator('[data-filter-item]:visible').count() == len(rows), f'reset {route}'
        if group == 'events':
            assert page.locator('#year').input_value() == '', 'année vide après reset'
    return checks


def audit_browser(browser, origin, out, data, builder, proof, report, axe_source):
    page = browser.new_page(viewport=dict(width=1440, height=1000), reduced_motion='reduce')
    page.set_default_timeout(15000)
    errors = report.setdefault('errors', [])
    js_errors = report.setdefault('javascriptErrors', [])
    page.on('pageerror', lambda error: js_errors.append(str(error)))
    # Même une régression ne doit pas déclencher de requête vers un tiers.
    page.route('**/*', lambda route: route.continue_() if route.request.url.startswith(origin + '/') else route.abort())
    routes = sorted('/' + p.parent.relative_to(out).as_posix().strip('/') + '/' if p.parent != out else '/' for p in out.rglob('index.html'))
    report['routes'] = routes
    editorial = {builder.href(group, row): row for group in builder.COLLECTIONS for row in data.get(group, []) if builder.published(row)}
    report['editorialNotesChecked'] = []
    cache, internal, external, fragments = {}, set(), set(), set()
    citations = []

    def check_link(base, value):
        target = urljoin(base, value)
        parsed = urlsplit(target)
        if parsed.scheme not in ('http', 'https'):
            raise AssertionError(f'href non HTTP(S) : {base} -> {value}')
        if (parsed.scheme, parsed.netloc) != ('http', urlsplit(origin).netloc):
            external.add(target)
            return
        resource = target.split('#', 1)[0]
        if resource not in cache:
            response = page.request.get(resource)
            assert response.status == 200, f'href {base} -> {target}: HTTP {response.status}'
            cache[resource] = response.text() if 'text/html' in response.headers.get('content-type', '') else None
        internal.add(resource.removeprefix(origin))
        if parsed.fragment:
            assert cache[resource] is not None, f'ancre sur ressource non HTML : {target}'
            check_fragment(cache[resource], parsed.fragment)
            fragments.add(target.removeprefix(origin))

    for route in routes:
        try:
            response = page.goto(origin + route)
            assert response.status == 200, f'HTTP {response.status}'
            assert page.locator('h1').count() == 1 and page.locator('main').count() == 1
            assert page.locator('html').get_attribute('lang') == 'fr'
            markup = page.content()
            row = editorial.get(route, {})
            if row.get('editorialNote'):
                assert builder.text(row['editorialNote']) in page.locator('.reading').inner_text(), 'note éditoriale absente'
                report['editorialNotesChecked'].append(route)
            if route in ('/', '/sources/'):
                notice = page.locator('.corpus-notice').inner_text()
                assert 'Corpus incomplet' in notice and 'sans validation historienne' in notice
                if not any(builder.published(e) and e['periodId'] == '1972-1982' for e in data['events']):
                    assert '1972–1982 : aucune fiche publiée' in notice
            scan = HTMLScan(markup)
            assert len(scan.ids) == len(set(scan.ids)), 'IDs HTML dupliqués'
            for value in scan.hrefs:
                check_link(page.url, value)
            for citation in page.locator('a.citation').all():
                href = citation.get_attribute('href')
                label = citation.inner_text()
                check_fragment(markup, href[1:])
                # Clique réellement chaque appel, pas uniquement un GET sans fragment.
                citation.click()
                assert unquote(urlsplit(page.url).fragment) == href[1:]
                item = page.locator('[id="' + href[1:] + '"]')
                assert item.locator('.citation-number').inner_text() == label
                assert item.locator('a').get_attribute('href').startswith(('http://', 'https://'))
                citations.append(dict(route=route, label=label, href=href))
        except Exception as error:
            errors.append(dict(stage='crawl', route=route, error=str(error)))
    report.update(internalHrefs=sorted(internal), fragmentHrefs=sorted(fragments), externalHrefsNotFetched=sorted(external), citations=citations)
    search_rows = json.loads((out / 'search-index.json').read_text())
    for stage, exercise in (('search', lambda: exercise_search(page, origin, search_rows)), ('filters', lambda: exercise_filters(page, origin, data, builder))):
        try:
            report[stage] = exercise()
        except Exception as error:
            errors.append(dict(stage=stage, error=str(error)))

    report['reflow'] = []
    axe_reports = report.setdefault('axe', [])
    for width in (320, 390, 1440):
        page.set_viewport_size(dict(width=width, height=1000))
        for route in routes:
            try:
                page.goto(origin + route)
                dimensions = page.evaluate('({scroll:document.documentElement.scrollWidth, viewport:innerWidth})')
                assert dimensions['scroll'] <= dimensions['viewport'], str(dimensions)
                report['reflow'].append(dict(route=route, width=width, passed=True))
            except Exception as error:
                errors.append(dict(stage='reflow', route=route, width=width, error=str(error)))
            if width in (390, 1440):
                try:
                    page.evaluate(axe_source)
                    result = page.evaluate("""async () => {const r=await axe.run(document,{runOnly:{type:'tag',values:['wcag2a','wcag2aa','wcag21a','wcag21aa']}});
                        return {violations:r.violations,incomplete:r.incomplete.map(x=>({id:x.id,nodes:x.nodes.map(n=>n.target)})),passes:r.passes.length};} """)
                    axe_reports.append(dict(route=route, width=width, **result))
                    if result['violations']:
                        errors.append(dict(stage='axe', route=route, width=width, violations=[v['id'] for v in result['violations']]))
                except Exception as error:
                    errors.append(dict(stage='axe', route=route, width=width, error=str(error)))

    targets = dict(home='/', frise='/frise/')
    targets['collectif'] = next(builder.href('people', r) for r in data['people'] if builder.published(r) and builder.collective(r))
    targets['sources'] = '/sources/'
    for name, group in (('personne', 'people'), ('parcours', 'journeys')):
        candidates = [r['url'] for r in search_rows if r['url'].startswith('/' + builder.ROUTES[group] + '/')]
        if group == 'people':
            individuals = {builder.href(group, r) for r in data.get(group, []) if not builder.collective(r)}
            candidates = [url for url in candidates if url in individuals]
        if candidates:
            targets[name] = candidates[0]
        else:
            errors.append(dict(stage='captures', error=f'aucune fiche publique pour {name}'))
    report['captures'] = []
    for size, width in (('mobile', 390), ('desktop', 1440)):
        page.set_viewport_size(dict(width=width, height=1000))
        for name, route in targets.items():
            page.goto(origin + route)
            path = proof / f'integration-real-corpus-{name}-{size}.png'
            page.screenshot(path=str(path), full_page=True)
            report['captures'].append(dict(route=route, width=width, path=str(path.relative_to(proof.parent))))
    assert len(report['reflow']) == len(routes) * 3, 'reflow incomplet'
    assert len(axe_reports) == len(routes) * 2, 'axe incomplet'
    page.close()


def run(root=ROOT, report=None):
    report = report if report is not None else {}
    report.update(status='running', scope='accepted real corpus only; no fixtures; no historical certification')
    corpus = root / 'research/corpus.json'
    if not corpus.is_file():
        report.update(status='skipped', reason='research/corpus.json absent')
        return report
    raw = corpus.read_bytes()
    report['corpusSha256'] = hashlib.sha256(raw).hexdigest()
    data = json.loads(raw)
    qa = root / '.qa'
    if not (qa / 'python/playwright').is_dir() or not (qa / 'axe.min.js').is_file():
        raise RuntimeError('QA locale incomplète dans .qa/ ; aucune installation automatique')
    sys.path.insert(0, str(qa / 'python'))
    os.environ['PLAYWRIGHT_BROWSERS_PATH'] = str(qa / 'browsers')
    from playwright.sync_api import sync_playwright
    builder = load_module('integration_builder', root / 'scripts/build.py')
    serving = load_module('integration_server', root / 'scripts/serve.py')
    proof = root / 'evidence'
    proof.mkdir(exist_ok=True)

    class QuietHandler(serving.PublicHandler):
        def log_message(self, *_):
            pass

    with tempfile.TemporaryDirectory(prefix='integration-real-', dir=qa) as tmp:
        out = Path(tmp)
        report['build'] = builder.build(data, out, root)
        handler = functools.partial(QuietHandler, directory=str(out))
        with ThreadingHTTPServer(('127.0.0.1', 0), handler) as server:
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            origin = f'http://127.0.0.1:{server.server_port}'
            try:
                with sync_playwright() as playwright:
                    browser = playwright.chromium.launch(headless=True, args=['--disable-dev-shm-usage'])
                    try:
                        audit_browser(browser, origin, out, data, builder, proof, report, (qa / 'axe.min.js').read_text())
                    finally:
                        browser.close()
            finally:
                server.shutdown()
                thread.join(timeout=5)
    assert hashlib.sha256(corpus.read_bytes()).hexdigest() == report['corpusSha256'], 'corpus modifié pendant la QA : relancer sur la version acceptée stable'
    report['status'] = 'failed' if report.get('errors') or report.get('javascriptErrors') else 'passed'
    return report


def main():
    proof = ROOT / 'evidence'
    proof.mkdir(exist_ok=True)
    report = {}
    try:
        run(ROOT, report)
    except Exception as error:
        report.update(status='failed', failure=f'{type(error).__name__}: {error}')
    (proof / 'integration-real-corpus-axe.json').write_text(json.dumps(report.pop('axe', []), ensure_ascii=False, indent=2))
    (proof / 'integration-real-corpus-report.json').write_text(json.dumps(report, ensure_ascii=False, indent=2))
    print(json.dumps({k: report[k] for k in ('status', 'reason', 'failure', 'corpusSha256', 'build') if k in report}, ensure_ascii=False, indent=2))
    if report.get('errors'):
        print(json.dumps(report['errors'], ensure_ascii=False, indent=2))
    return int(report['status'] == 'failed')


if __name__ == '__main__':
    raise SystemExit(main())
