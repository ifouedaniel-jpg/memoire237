"""Outillage QA optionnel, tous téléchargements et caches dans .qa/ du projet."""
import base64
import hashlib
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tarfile
from urllib.request import urlopen
import zipfile

ROOT = Path(__file__).resolve().parents[1]
QA = ROOT / '.qa'


def get(url):
    with urlopen(url, timeout=90) as response:
        return response.read()


def main():
    QA.mkdir(exist_ok=True)
    metadata = json.loads(get('https://pypi.org/pypi/pip/26.3/json'))
    wheel = next(x for x in metadata['urls'] if x['filename'].endswith('.whl'))
    blob = get(wheel['url'])
    if hashlib.sha256(blob).hexdigest() != wheel['digests']['sha256']:
        raise ValueError('Intégrité pip invalide')
    runtime = QA / 'pip-runtime'
    runtime.mkdir(exist_ok=True)
    with zipfile.ZipFile(io.BytesIO(blob)) as z:
        for name in z.namelist():
            if name.startswith('/') or '..' in Path(name).parts:
                raise ValueError('Wheel invalide')
        z.extractall(runtime)
    env = dict(os.environ, PYTHONPATH=str(runtime), PIP_CACHE_DIR=str(QA / 'pip-cache'), PLAYWRIGHT_BROWSERS_PATH=str(QA / 'browsers'))
    subprocess.run([sys.executable, '-m', 'pip', 'install', '--upgrade', '--target', str(QA / 'python'), 'playwright==1.65.2', 'greenlet==3.5.6'], env=env, check=True)
    env['PYTHONPATH'] = str(QA / 'python')
    subprocess.run([sys.executable, '-m', 'playwright', 'install', 'chromium'], env=env, check=True)
    package = json.loads(get('https://registry.npmjs.org/axe-core/4.14.1'))
    archive = get(package['dist']['tarball'])
    integrity = 'sha512-' + base64.b64encode(hashlib.sha512(archive).digest()).decode()
    if integrity != package['dist']['integrity']:
        raise ValueError('Intégrité axe-core invalide')
    with tarfile.open(fileobj=io.BytesIO(archive), mode='r:gz') as tar:
        member = tar.extractfile('package/axe.min.js')
        if member is None:
            raise ValueError('axe.min.js absent du paquet officiel')
        (QA / 'axe.min.js').write_bytes(member.read())
    (QA / 'provenance.json').write_text(json.dumps(dict(playwright='1.65.2', greenlet='3.5.6', axe='4.14.1', axeIntegrity=integrity, pip=metadata['info']['version']), indent=2))
    print('QA prête dans .qa/ uniquement ; aucun logiciel système installé.')


if __name__ == '__main__':
    main()
