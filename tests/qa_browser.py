"""Contrôles navigateur réels ; corpus exclusivement fictif en dossier temporaire."""
import functools
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
import importlib.util
import json
from pathlib import Path
import tempfile
import threading
import sys
from playwright.sync_api import sync_playwright
from test_site import fixture, ROOT

spec = importlib.util.spec_from_file_location('builder', ROOT / 'scripts/build.py')
builder = importlib.util.module_from_spec(spec)
spec.loader.exec_module(builder)
server_spec = importlib.util.spec_from_file_location('public_server', ROOT / 'scripts/serve.py')
server_module = importlib.util.module_from_spec(server_spec)
server_spec.loader.exec_module(server_module)


class QuietHandler(server_module.PublicHandler):
    def log_message(self, *_):
        pass


def main():
    proof = ROOT / 'evidence'
    proof.mkdir(exist_ok=True)
    data = fixture()
    base = data['events'][0]
    data['events'].append(dict(base, id='e2', slug='autre-fictif', title='Autre test fictif', category='Autre', date=dict(startYear=2000, label='2000 (fictif)', precision='year'), periodId='2000-now'))
    data['people'] = [dict(base, id='p1', slug='personne-fictive', title='Personne fictive')]
    data['places'] = [dict(base, id='l1', slug='lieu-fictif', title='Lieu fictif', lat=5, lon=11, modernMap=True)]
    data['themes'] = [dict(base, id='t1', slug='theme-fictif', title='Thème fictif')]
    data['events'][0].update(personIds=['p1'], placeIds=['l1'], themeIds=['t1'])
    data['journeys'] = [dict(base, id='j1', slug='parcours-fictif', title='Parcours fictif', steps=[dict(type='event', id='e1'), dict(type='person', id='p1')], durationMinutes=10)]
    results = []
    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp)
        builder.build(data, out, ROOT)
        handler = functools.partial(QuietHandler, directory=str(out))
        server = ThreadingHTTPServer(('127.0.0.1', 0), handler)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        origin = 'http://127.0.0.1:' + str(server.server_port)
        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True, args=['--disable-dev-shm-usage'])
                page = browser.new_page(viewport=dict(width=1440, height=1000), reduced_motion='reduce')
                errors = []
                page.on('pageerror', lambda e: errors.append(str(e)))
                page.goto(origin + '/frise/')
                assert page.locator('[data-filter-item]:visible').count() == 2
                page.locator('#year').fill('1901')
                page.get_by_role('button', name='Filtrer', exact=True).click()
                assert page.locator('[data-filter-item]:visible').count() == 1, 'filtre année/plage'
                page.locator('#year').fill('1950')
                page.get_by_role('button', name='Filtrer', exact=True).click()
                assert page.locator('[data-filter-item]:visible').count() == 0, 'année vide de résultats'
                assert page.locator('[data-filter-empty]').is_visible()
                page.get_by_role('button', name='Réinitialiser').click()
                assert page.locator('[data-filter-item]:visible').count() == 2, 'année input vide = tout'
                page.locator('#period').select_option('2000-now')
                page.get_by_role('button', name='Filtrer', exact=True).click()
                assert page.locator('[data-filter-item]:visible').count() == 1
                page.locator('#category').select_option('Test')
                page.get_by_role('button', name='Filtrer', exact=True).click()
                assert page.locator('[data-filter-item]:visible').count() == 0, 'combinaison filtres'
                page.goto(origin + '/frise/?year=1901')
                assert page.locator('[data-filter-item]:visible').count() == 1, 'URL filtres partageable'
                results += ['filtres année/plage/période/catégorie/combinaison/réinitialisation/URL']
                page.goto(origin + '/recherche/?q=evenement')
                page.wait_for_selector('[data-search-results] a')
                assert 'Événement fictif' in page.locator('[data-search-results]').inner_text()
                page.locator('#q').fill('INEXISTANTZZZZ')
                page.get_by_role('button', name='Rechercher', exact=True).click()
                page.wait_for_function("document.querySelector('[data-search-status]').textContent.includes('Aucun')")
                assert page.locator('[data-search-results] a').count() == 0
                results += ['recherche accents/casse/URL/absence de résultats']
                page.goto(origin + '/')
                page.keyboard.press('Tab')
                assert page.locator('.skip').evaluate('(e)=> e===document.activeElement'), 'lien évitement clavier'
                assert page.locator('.skip').evaluate('(e)=>getComputedStyle(e).outlineStyle') != 'none'
                page.keyboard.press('Enter')
                assert page.evaluate("document.activeElement.id") == 'contenu'
                results += ['clavier : lien évitement et focus visible']
                # Crawl exact : tous les liens internes générés + sémantique de base.
                routes = ['/', '/frise/', '/personnalites/', '/themes/', '/lieux/', '/parcours/', '/sources/', '/a-propos/', '/recherche/']
                routes += [builder.href(k, row) for k in builder.COLLECTIONS for row in data[k]]
                checked = set()
                for route in routes:
                    page.goto(origin + route)
                    assert page.locator('h1').count() == 1, route
                    assert page.locator('main').count() == 1
                    assert page.locator('html').get_attribute('lang') == 'fr'
                    for link in page.locator('a[href^="/"]').evaluate_all('(xs)=>xs.map(x=>x.getAttribute("href"))'):
                        if link not in checked:
                            assert page.request.get(origin + link).status == 200, link
                            checked.add(link)
                results += [f'navigation : {len(routes)} pages, {len(checked)} cibles internes sans lien cassé']
                page.goto(origin + '/')
                page.get_by_role('link', name='Suivre un parcours →').click()
                page.get_by_role('link', name='Parcours fictif', exact=True).click()
                page.locator('.steps').get_by_role('link', name='Événement fictif', exact=True).click()
                page.locator('.related').get_by_role('link', name='Personne fictive', exact=True).click()
                assert page.locator('.source-box').get_by_role('link', name='Source fictive', exact=True).get_attribute('href') == 'https://example.org/test'
                results += ['parcours cliqué : accueil → parcours → événement → personne → référence source']
                nojs = browser.new_context(java_script_enabled=False, viewport=dict(width=390, height=844))
                fallback = nojs.new_page()
                fallback.goto(origin + '/frise/')
                assert fallback.locator('.card').count() == 2
                fallback.get_by_role('link', name='Événement fictif', exact=True).click()
                assert fallback.locator('h1').inner_text() == 'Événement fictif'
                nojs.close()
                results += ['sans JavaScript : répertoire et détail navigables']
                # Vérifie tous les gabarits en mobile et desktop, pas uniquement l’accueil.
                for width in (320, 360, 390, 768, 1440):
                    page.set_viewport_size(dict(width=width, height=1000))
                    for route in routes:
                        page.goto(origin + route)
                        assert page.evaluate('document.documentElement.scrollWidth <= innerWidth'), f'débordement {width} {route}'
                results += ['responsive : tous gabarits à 320, 360, 390, 768 et 1440 px sans débordement']
                axe_source = (ROOT / '.qa/axe.min.js').read_text()
                axe_reports = []
                for width in (390, 1440):
                    page.set_viewport_size(dict(width=width, height=1000))
                    for route in routes:
                        page.goto(origin + route)
                        page.evaluate(axe_source)
                        report = page.evaluate("async () => {const r=await axe.run(document,{runOnly:{type:'tag',values:['wcag2a','wcag2aa','wcag21a','wcag21aa']}});return {violations:r.violations,incomplete:r.incomplete.map(x=>x.id),passes:r.passes.length};}")
                        axe_reports.append(dict(route=route, width=width, **report))
                (proof / 'axe-report.json').write_text(json.dumps(axe_reports, ensure_ascii=False, indent=2))
                violations = [(r['route'], v['id']) for r in axe_reports for v in r['violations']]
                assert not violations, violations
                results += [f'axe-core WCAG 2.1 AA : {len(routes)} pages à 390 et 1440 px, aucune violation automatique']
                assert not errors, errors
                results += ['aucune erreur JavaScript']
                # Captures du VRAI build sans aucune fixture livrée.
                public_dir = ROOT / 'dist'
                if public_dir.exists():
                    actual = ThreadingHTTPServer(('127.0.0.1', 0), functools.partial(QuietHandler, directory=str(public_dir)))
                    threading.Thread(target=actual.serve_forever, daemon=True).start()
                    try:
                        for name, width in [('desktop', 1440), ('mobile', 390)]:
                            page.set_viewport_size(dict(width=width, height=1000))
                            page.goto(f'http://127.0.0.1:{actual.server_port}/')
                            page.screenshot(path=str(proof / f'home-{name}.png'), full_page=True)
                    finally:
                        actual.shutdown()
                        actual.server_close()
                browser.close()
        finally:
            server.shutdown()
            server.server_close()
    (proof / 'browser-report.json').write_text(json.dumps(dict(status='passed', checks=results), ensure_ascii=False, indent=2))
    print(json.dumps(results, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
