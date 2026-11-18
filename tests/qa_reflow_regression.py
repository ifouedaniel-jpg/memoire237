"""Tight real-corpus reflow probe, before/after DOM and screenshots."""
import json
import sys
from pathlib import Path
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
ROUTES = ['/evenements/comite-olympique/', '/evenements/racam/', '/personnalites/udefec/', '/themes/independances/']

def main():
    label = sys.argv[1] if len(sys.argv) > 1 else 'after'
    proof = ROOT / 'evidence' / ('reflow-' + label)
    proof.mkdir(exist_ok=True)
    results = []
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, args=['--disable-dev-shm-usage'])
        page = browser.new_page(viewport={'width': 320, 'height': 1000}, reduced_motion='reduce')
        for route in ROUTES:
            page.goto('http://127.0.0.1:8237' + route)
            before = page.evaluate('''() => ({scroll:document.documentElement.scrollWidth, viewport:innerWidth,
                elements:[...document.querySelectorAll('main *')].map(e=>{const r=e.getBoundingClientRect(),s=getComputedStyle(e);return {tag:e.tagName,cls:e.className,text:e.textContent.slice(0,180),left:r.left,right:r.right,width:r.width,scroll:e.scrollWidth,minWidth:s.minWidth,overflowWrap:s.overflowWrap}}).filter(e=>e.right>innerWidth || e.scroll>e.width+1)})''')
            page.screenshot(path=str(proof / (route.strip('/').replace('/', '-') + '.png')), full_page=True)
            # Single-variable experiment: break long heading words, no clipping.
            page.evaluate("document.styleSheets[0].insertRule('.page-heading h1 {overflow-wrap:anywhere}', document.styleSheets[0].cssRules.length)")
            experiment = page.evaluate('document.documentElement.scrollWidth')
            results.append(dict(route=route, **before, headingWrapExperiment=experiment))
        browser.close()
    (proof / 'dom.json').write_text(json.dumps(results, ensure_ascii=False, indent=2))
    print(json.dumps(results, ensure_ascii=False, indent=2))
    assert all(r['scroll'] <= r['viewport'] for r in results), 'real 320px reflow regression'

if __name__ == '__main__':
    main()
