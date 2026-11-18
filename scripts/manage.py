"""Commandes locales uniquement. Restauration vers une copie neuve sous restored/."""
import argparse
from datetime import datetime, timezone
import fcntl
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import secrets
import shutil
import signal
import subprocess
import sys
import tempfile
import time
from urllib.request import urlopen
import zipfile

ROOT = Path(__file__).resolve().parents[1]
BACKUP_DIRS = ('scripts', 'assets', 'tests', 'docs', 'research')


def digest(data):
    return hashlib.sha256(data).hexdigest()


def backup(root=ROOT):
    root = root.resolve()
    folder = root / 'backups'
    folder.mkdir(mode=0o700, exist_ok=True)
    archive = folder / (datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S') + '-' + secrets.token_hex(3) + '.zip')
    files = [p for p in root.iterdir() if p.is_file() and (p.suffix in ('.md', '.json') or p.name == '.gitignore')]
    for name in BACKUP_DIRS:
        directory = root / name
        if directory.is_dir() and not directory.is_symlink():
            files.extend(p for p in directory.rglob('*') if p.is_file() and '__pycache__' not in p.parts)
    manifest = {}
    payload = []
    for p in sorted(files):
        if p.is_symlink() or not p.resolve().is_relative_to(root):
            raise ValueError(f'Lien symbolique refusé : {p}')
        relative = p.relative_to(root).as_posix()
        content = p.read_bytes()
        manifest[relative] = digest(content)
        payload.append((relative, content))
    fd = os.open(archive, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    with os.fdopen(fd, 'wb') as handle, zipfile.ZipFile(handle, 'w', zipfile.ZIP_DEFLATED) as z:
        for name, content in payload:
            z.writestr(name, content)
        z.writestr('MANIFEST.json', json.dumps(dict(version=1, files=manifest), indent=2))
    print(f'Sauvegarde privée : {archive} ({len(manifest)} fichiers)')
    return archive


def restore(archive, destination, root=ROOT):
    root = root.resolve()
    destination = destination.resolve()
    allowed = root / 'restored'
    if not destination.is_relative_to(allowed) or destination == allowed or destination.exists():
        raise ValueError('Restauration uniquement vers une copie inexistante sous restored/ ; aucun écrasement')
    with zipfile.ZipFile(archive) as z:
        infos = z.infolist()
        names = [i.filename for i in infos]
        if len(names) > 10000 or sum(i.file_size for i in infos) > 100_000_000 or len(names) != len(set(names)):
            raise ValueError('Archive trop volumineuse ou noms dupliqués')
        for info in infos:
            path = PurePosixPath(info.filename)
            if path.is_absolute() or '..' in path.parts or '\\' in info.filename or info.is_dir() or (info.external_attr >> 16) & 0o170000 == 0o120000:
                raise ValueError('Chemin ou lien interdit dans archive')
        try:
            manifest = json.loads(z.read('MANIFEST.json'))
            if manifest.get('version') != 1 or set(names) != set(manifest['files']) | {'MANIFEST.json'}:
                raise ValueError('Manifest incohérent')
            content = {name:z.read(name) for name in manifest['files']}
            if any(digest(payload) != manifest['files'][name] for name, payload in content.items()):
                raise ValueError('Intégrité SHA256 invalide')
        except (KeyError, TypeError, json.JSONDecodeError) as exc:
            raise ValueError('Manifest absent ou invalide') from exc
        destination.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix='.restore-', dir=destination.parent) as tmp:
            for name, payload in content.items():
                path = Path(tmp) / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(payload)
            Path(tmp).rename(destination)
    print(f'Copie restaurée et vérifiée : {destination} ({len(content)} fichiers)')
    return destination


def state():
    try:
        result = json.loads((ROOT / '.run/server.json').read_text())
        command = Path(f'/proc/{result["pid"]}/cmdline').read_bytes().split(b'\0')
        if str(ROOT / 'scripts/serve.py').encode() not in command or result['token'].encode() not in command or result['root'] != str(ROOT):
            return None
        return result
    except (OSError, ValueError, KeyError, TypeError):
        return None


def start(port):
    current = state()
    if current:
        print(f'Déjà démarré : http://127.0.0.1:{current["port"]} PID={current["pid"]}')
        return current
    if not (ROOT / 'dist/build-report.json').is_file():
        subprocess.run([sys.executable, str(ROOT / 'scripts/build.py')], check=True)
    run = ROOT / '.run'
    run.mkdir(mode=0o700, exist_ok=True)
    token = secrets.token_hex(16)
    with (run / 'server.log').open('ab') as log:
        process = subprocess.Popen([sys.executable, str(ROOT / 'scripts/serve.py'), '--port', str(port), '--token', token, '--state', str(run / 'server.json')], cwd=ROOT, stdout=log, stderr=log, start_new_session=True)
    for _ in range(100):
        current = state()
        if process.poll() is not None:
            raise RuntimeError('Démarrage échoué ; voir .run/server.log. Port occupé ? Utiliser --port 0.')
        if current and current['token'] == token:
            try:
                with urlopen(f'http://127.0.0.1:{current["port"]}/', timeout=1) as response:
                    if response.status == 200:
                        print(f'Démarré : http://127.0.0.1:{current["port"]} PID={current["pid"]}')
                        return current
            except OSError:
                pass
        time.sleep(.05)
    process.terminate()
    process.wait(timeout=5)
    raise RuntimeError('Délai de démarrage dépassé')


def stop():
    current = state()
    if not current:
        print('Aucun serveur appartenant à ce projet en cours ; aucun signal envoyé.')
        return
    os.kill(current['pid'], signal.SIGTERM)
    for _ in range(100):
        if not state():
            (ROOT / '.run/server.json').unlink(missing_ok=True)
            print('Serveur du projet arrêté.')
            return
        time.sleep(.05)
    raise RuntimeError('Arrêt non confirmé ; aucun SIGKILL automatique')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    for action in ('start', 'restart'):
        p = sub.add_parser(action)
        p.add_argument('--port', type=int, default=8237, help='0 = port libre choisi par le système')
    for action in ('stop', 'status', 'backup', 'build', 'serve'):
        sub.add_parser(action)
    p = sub.add_parser('restore')
    p.add_argument('archive', type=Path)
    p.add_argument('destination', type=Path)
    args = parser.parse_args()
    run = ROOT / '.run'
    run.mkdir(mode=0o700, exist_ok=True)
    with (run / 'manage.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        if args.command == 'backup':
            backup()
        elif args.command == 'restore':
            restore(args.archive, args.destination)
        elif args.command == 'build':
            subprocess.run([sys.executable, str(ROOT / 'scripts/build.py')], check=True)
        elif args.command == 'serve':
            subprocess.run([sys.executable, str(ROOT / 'scripts/serve.py')], check=True)
        elif args.command == 'status':
            print(json.dumps(state(), indent=2))
        elif args.command == 'stop':
            stop()
        else:
            if args.command == 'restart':
                stop()
            start(args.port)


if __name__ == '__main__':
    try:
        main()
    except (ValueError, RuntimeError, OSError, zipfile.BadZipFile) as exc:
        raise SystemExit(str(exc))
