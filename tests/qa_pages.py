"""QA sous-chemin sur le corpus réel ; --url pour vérifier la publication exacte.

Prérequis : outils QA locaux existants ; ne télécharge rien.
"""
import argparse
import functools
import hashlib
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import importlib.util
import json
from pathlib import Path
import sys
import threading
from types import SimpleNamespace
from urllib.parse import urljoin, urlsplit

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tests'))
from qa_real_corpus import check_fragment, exercise_filters, exercise_search


def run(url=None):
    spec = importlib.util.spec_from_file_location('builder_pages', ROOT / 'scripts/build.py')
    builder = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(builder)
    from playwright.sync_api import sync_playwright
    data_bytes = (ROOT / 'research/corpus.json').read_bytes()
    data = json.loads(data_bytes)
    public_url = 'https://ifouedaniel-jpg.github.io/memoire237'
    stage = ROOT / '.publication/site'
    out = stage / 'memoire237'
    out.mkdir(parents=True, exist_ok=True)
    counts = builder.build(data, out, ROOT, base_url=public_url)
    assert counts['pages'] == 75 and counts['sources'] == 25, counts
    server = None
    if url is None:
        class Quiet(SimpleHTTPRequestHandler):
            def log_message(self, *_):
                pass
        server = ThreadingHTTPServer(('127.0.0.1', 0), functools.partial(Quiet, directory=str(stage)))
        threading.Thread(target=server.serve_forever, daemon=True).start()
        url = f'http://127.0.0.1:{server.server_port}/memoire237'
    base = url.rstrip('/')
    origin = urlsplit(base).scheme + '://' + urlsplit(base).netloc
    prefix = urlsplit(base).path
    routes = sorted('/' + p.parent.relative_to(out).as_posix() + '/' if p.parent != out else '/' for p in out.rglob('index.html'))
    report = dict(url=base, corpusSha256=hashlib.sha256(data_bytes).hexdigest(), counts=counts, routes=routes, javascriptErrors=[], failedResponses=[], reflow=[], assets=[], citations=0, internalLinks=0)
    checked = set()
    try:
        with sync_playwright() as pw:
            browser = pw.chromium.launch(headless=True)
            page = browser.new_page(viewport=dict(width=1440, height=1000), reduced_motion='reduce')
            page.on('pageerror', lambda e: report['javascriptErrors'].append(str(e)))
            page.on('response', lambda r: report['failedResponses'].append(dict(url=r.url,status=r.status)) if r.status >= 400 else None)
            page.route('**/*', lambda r: r.continue_() if r.request.url.startswith(origin + prefix + '/') else r.abort())
            for route in routes:
                response = page.goto(base + route)
                assert response.status == 200, (route, response.status)
                assert page.locator('h1').count() == 1
                assert page.locator('link[rel=canonical]').get_attribute('href') == public_url + route
                markup = page.content()
                for value in page.locator('a[href],link[href],script[src]').evaluate_all('(xs)=>xs.map(x=>x.getAttribute("href")||x.getAttribute("src"))'):
                    parsed = urlsplit(urljoin(page.url, value))
                    if parsed.netloc != urlsplit(origin).netloc:
                        continue
                    assert parsed.path.startswith(prefix + '/'), value
                    if parsed.fragment:
                        check_fragment(markup, parsed.fragment)
                    key = parsed.path
                    if key not in checked:
                        r = page.request.get(origin + key)
                        assert r.status == 200, (key, r.status)
                        checked.add(key)
                for citation in page.locator('a.citation').all():
                    target = citation.get_attribute('href')[1:]
                    citation.click()
                    assert urlsplit(page.url).fragment == target
                    assert page.locator(f'[id="{target}"] .citation-number').inner_text() == citation.inner_text()
                    report['citations'] += 1
            for width in (320, 390, 1440):
                page.set_viewport_size(dict(width=width, height=1000))
                for route in routes:
                    page.goto(base + route)
                    assert page.evaluate('document.documentElement.scrollWidth <= innerWidth'), (route, width)
                    report['reflow'].append(dict(route=route,width=width))
            rows = json.loads((out / 'search-index.json').read_text())
            report['search'] = exercise_search(page, base, rows)
            adapter = SimpleNamespace(published=builder.published, PERIODS=builder.PERIODS, href=lambda g,r: prefix + builder.href(g,r))
            report['filters'] = exercise_filters(page, base, data, adapter)
            report['internalLinks'] = len(checked)
            for asset in ('assets/style.css', 'assets/app.js', 'assets/icon.svg', 'search-index.json'):
                r = page.request.get(base + '/' + asset)
                assert r.status == 200
                assert r.body() == (out / asset).read_bytes(), asset
                report['assets'].append(dict(path=asset,status=r.status,sha256=hashlib.sha256(r.body()).hexdigest()))
            proof = ROOT / 'evidence/pages'
            proof.mkdir(parents=True, exist_ok=True)
            for width,label in ((1440,'desktop'),(390,'mobile')):
                page.set_viewport_size(dict(width=width,height=1000))
                page.goto(base + '/')
                page.screenshot(path=str(proof / f'{"public" if server is None else "local"}-{label}.png'), full_page=True)
            browser.close()
        assert not report['javascriptErrors'], report['javascriptErrors']
        assert not report['failedResponses'], report['failedResponses']
        assert len(report['routes']) == 75 and len(report['reflow']) == 225
        assert hashlib.sha256((ROOT / 'research/corpus.json').read_bytes()).hexdigest() == report['corpusSha256']
        report['status'] = 'passed'
        dest = ROOT / f'evidence/pages/{"public" if server is None else "local"}-report.json'
        dest.write_text(json.dumps(report, ensure_ascii=False, indent=2))
        print(json.dumps({k:v for k,v in report.items() if k not in ('routes','reflow','filters')},ensure_ascii=False,indent=2))
    finally:
        if server:
            server.shutdown()
            server.server_close()


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--url')
    run(p.parse_args().url)
