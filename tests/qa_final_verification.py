"""Read-only final local integration and confidentiality checks."""
import hashlib
import json
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parents[1]
EXPECTED = 'f34054dcd0c070ca3616c75761a06b6e61f05440f103a3af2dd47b0e68618a3d'


def main():
    digest = hashlib.sha256((ROOT / 'research/corpus.json').read_bytes()).hexdigest()
    assert digest == EXPECTED
    qa = json.loads((ROOT / 'evidence/integration-real-corpus-report.json').read_text())
    historic = json.loads((ROOT / 'evidence/reflow-before/integration-real-corpus-report.json').read_text())
    assert historic['status'] == 'failed' and len([e for e in historic['errors'] if e['stage'] == 'reflow']) == 4
    assert qa['status'] == 'passed' and not qa['errors'] and not qa['javascriptErrors']
    assert len(qa['routes']) == 75 and len(qa['reflow']) == 225
    out = ROOT / 'dist'
    files = [p.relative_to(out).as_posix() for p in out.rglob('*') if p.is_file()]
    assert all(not p.is_symlink() for p in out.rglob('*'))
    assert all(not name.startswith(('research/', 'evidence/', 'backups/', 'restored/', '.qa/')) for name in files)
    fixture_markers = ('Résumé fictif de test', 'Texte fictif, sans valeur historique.', 'Source fictive', 'Événement fictif')
    assert not any(marker in p.read_text() for p in out.rglob('*.html') for marker in fixture_markers)
    origin = 'http://127.0.0.1:8237'
    codes = {}
    for route, expected in [('/', 200), ('/sources/', 200), ('/personnalites/assale/', 200), ('/personnalites/udefec/', 200), ('/personnalites/moume-etia/', 404), ('/research/corpus.json', 404), ('/research/corpus-candidate.json', 404), ('/evidence/', 404), ('/backups/', 404), ('/build-report.json', 404)]:
        try:
            with urlopen(origin + route) as response:
                status = response.status
                assert "default-src 'self'" in response.headers['Content-Security-Policy']
        except HTTPError as error:
            status = error.code
        assert status == expected, (route, status)
        codes[route] = status
    sockets = [line.split() for line in Path('/proc/net/tcp').read_text().splitlines()[1:]]
    listening = [row[1] for row in sockets if row[1].endswith(':202D') and row[3] == '0A']
    assert listening == ['0100007F:202D'], listening
    operations = json.loads((ROOT / 'evidence/operations-report.json').read_text())
    restored = Path(operations['restored'])
    assert (restored / 'research/corpus.json').read_bytes() == (ROOT / 'research/corpus.json').read_bytes()
    assert json.loads((restored / 'dist/build-report.json').read_text()) == qa['build']
    report = dict(status='passed', corpusSha256=digest, build=qa['build'], historicFailurePreserved=True, http=codes, listen= '127.0.0.1:8237', artifactFiles=len(files), artifactBytes=sum((out / f).stat().st_size for f in files), noPrivatePathsOrFixtureHTML=True, restoredCorpusIdentical=True, restoredBuildIdentical=True, archive=operations['archive'], restored=operations['restored'])
    (ROOT / 'evidence/integration-final-verification.json').write_text(json.dumps(report, ensure_ascii=False, indent=2))
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
