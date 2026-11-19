"""Read-only domain QA against prepared bytes, without rebuilding."""
import concurrent.futures
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
from urllib.request import urlopen
from playwright.sync_api import sync_playwright

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tests'))
from qa_real_corpus import exercise_filters, exercise_search
BASE=sys.argv[1].rstrip('/') if len(sys.argv)>1 else 'https://saneahair.com'
OUT=ROOT/'.publication/domain/site'
PROOF=ROOT/'evidence/domain'
spec=importlib.util.spec_from_file_location('domain_builder',ROOT/'scripts/build.py')
builder=importlib.util.module_from_spec(spec)
spec.loader.exec_module(builder)
raw=(ROOT/'research/corpus.json').read_bytes()
data=json.loads(raw)
prep=json.loads((ROOT/'.publication/domain/preparation-report.json').read_text())
assert hashlib.sha256(raw).hexdigest()==prep['corpusSha256']
assert prep['counts']['publicCounts']==dict(events=37,people=7,places=10,themes=9,journeys=1)
report=dict(url=BASE,canonical='https://saneahair.com',corpusSha256=prep['corpusSha256'],counts=prep['counts'],routes=[],javascriptErrors=[],failedResponses=[],reflow=0)
with sync_playwright() as pw:
    browser=pw.chromium.launch(headless=True)
    page=browser.new_page(viewport=dict(width=390,height=1000))
    page.on('pageerror',lambda e:report['javascriptErrors'].append(str(e)))
    page.on('response',lambda r:report['failedResponses'].append(dict(url=r.url,status=r.status)) if r.status>=400 else None)
    for f in sorted(OUT.rglob('index.html')):
        route='/' if f.parent==OUT else '/'+f.parent.relative_to(OUT).as_posix()+'/'
        response=page.goto(BASE+route)
        assert response.status==200,(route,response.status)
        assert page.locator('link[rel=canonical]').get_attribute('href')=='https://saneahair.com'+route
        assert '/memoire237/' not in page.content()
        for width in (320,390,1440):
            page.set_viewport_size(dict(width=width,height=1000))
            assert page.evaluate('document.documentElement.scrollWidth<=innerWidth'),(route,width)
            report['reflow']+=1
        report['routes'].append(route)
    report['search']=exercise_search(page,BASE,json.loads((OUT/'search-index.json').read_text()))
    report['filters']=exercise_filters(page,BASE,data,builder)
    for width,label in ((1440,'desktop'),(390,'mobile')):
        page.set_viewport_size(dict(width=width,height=1000))
        page.goto(BASE+'/')
        page.screenshot(path=str(PROOF/('domain-'+label+'.png')),full_page=True)
    browser.close()
assert len(report['routes'])==75 and report['reflow']==225
assert not report['javascriptErrors'] and not report['failedResponses'],report
manifest=json.loads((ROOT/'.publication/domain/manifest.json').read_text())
def verify(item):
    with urlopen(BASE+'/'+item['path'],timeout=30) as response:
        raw=response.read()
        assert response.status==200
        assert hashlib.sha256(raw).hexdigest()==item['sha256'],item['path']
    return dict(path=item['path'],status=200,sha256=item['sha256'])
with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
    report['files']=list(pool.map(verify,manifest))
assert len(report['files'])==84
report['status']='passed'
(PROOF/'public-report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2))
print(json.dumps(dict(status=report['status'],url=BASE,routes=len(report['routes']),reflow=report['reflow'],files=len(report['files']),searches=len(report['search']),filters=len(report['filters']),counts=report['counts'],javascriptErrors=report['javascriptErrors'])))
