"""Exercice réel backup/restore/build/start/restart/stop dans une copie isolée."""
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
from pathlib import Path
import secrets
import subprocess
import sys
from urllib.error import HTTPError
from urllib.request import urlopen
import zipfile

ROOT = Path(__file__).resolve().parents[1]


def main():
    spec = importlib.util.spec_from_file_location('manager', ROOT / 'scripts/manage.py')
    manager = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(manager)
    archive = manager.backup(ROOT)
    destination = ROOT / 'restored' / ('verification-' + datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S') + '-' + secrets.token_hex(3))
    manager.restore(archive, destination, ROOT)
    with zipfile.ZipFile(archive) as z:
        manifest = json.loads(z.read('MANIFEST.json'))['files']
        for name, expected in manifest.items():
            actual = hashlib.sha256((destination / name).read_bytes()).hexdigest()
            assert actual == expected, name

    commands = []
    def run(*args):
        command = [sys.executable, *map(str, args)]
        result = subprocess.run(command, cwd=destination, text=True, capture_output=True)
        commands.append(dict(command=command, returncode=result.returncode, stdout=result.stdout, stderr=result.stderr))
        assert result.returncode == 0, result.stderr
        return result.stdout

    report = dict(archive=str(archive), restored=str(destination), restoredFiles=len(manifest), checks=[], commands=commands)
    try:
        run(destination / 'scripts/build.py')
        run(destination / 'scripts/manage.py', 'start', '--port', '0')
        initial = json.loads(run(destination / 'scripts/manage.py', 'status'))
        origin = f'http://127.0.0.1:{initial["port"]}'
        with urlopen(origin) as response:
            assert response.status == 200
            assert 'frame-ancestors' in response.headers['Content-Security-Policy']
            assert response.headers['X-Content-Type-Options'] == 'nosniff'
        assert any(line.split()[1] == f'0100007F:{initial["port"]:04X}' and line.split()[3] == '0A' for line in Path('/proc/net/tcp').read_text().splitlines()[1:]), 'socket non loopback'
        protected = ['/research/corpus.json', '/research/corpus-candidate.json', '/research/', '/scripts/build.py', '/backups/', '/.git/config', '/build-report.json', '/assets/']
        statuses = {}
        for path in protected:
            try:
                urlopen(origin + path)
                raise AssertionError('Chemin privé exposé : ' + path)
            except HTTPError as exc:
                assert exc.code == 404
                statuses[path] = exc.code
        run(destination / 'scripts/manage.py', 'restart', '--port', '0')
        restarted = json.loads(run(destination / 'scripts/manage.py', 'status'))
        assert restarted['pid'] != initial['pid']
        with urlopen(f'http://127.0.0.1:{restarted["port"]}/') as response:
            assert response.status == 200
        run(destination / 'scripts/manage.py', 'stop')
        assert json.loads(run(destination / 'scripts/manage.py', 'status')) is None
        # Idempotence : aucun signal si déjà arrêté.
        run(destination / 'scripts/manage.py', 'stop')
        report.update(status='passed', initialPid=initial['pid'], restartPid=restarted['pid'], deniedPaths=statuses, checks=['manifest SHA256 tous fichiers identique', 'build reconstruit depuis copie isolée', 'socket LISTEN 127.0.0.1 vérifié dans /proc/net/tcp', 'HTTP200 + CSP/nosniff', '8 chemins privés/listing refusés HTTP404', 'restart change de PID et répond HTTP200', 'stop confirmé et idempotent'])
    finally:
        subprocess.run([sys.executable, str(destination / 'scripts/manage.py'), 'stop'], cwd=destination, check=False, capture_output=True)
        (ROOT / 'evidence').mkdir(exist_ok=True)
        (ROOT / 'evidence/operations-report.json').write_text(json.dumps(report, ensure_ascii=False, indent=2))
    print(json.dumps({k:v for k,v in report.items() if k != 'commands'}, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
