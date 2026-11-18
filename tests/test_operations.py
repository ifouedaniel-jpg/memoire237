import functools
from http.server import ThreadingHTTPServer
import importlib.util
import io
import json
from pathlib import Path
import tempfile
import threading
import unittest
from urllib.request import urlopen
from urllib.error import HTTPError
import zipfile

ROOT = Path(__file__).resolve().parents[1]


def load(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / f'scripts/{name}.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class OperationsTest(unittest.TestCase):
    def test_server_never_exposes_private_or_symlinks(self):
        server_module = load('serve')
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            public = root / 'dist'
            public.mkdir()
            (root / 'secret.json').write_text('PRIVATE-SECRET')
            (public / 'index.html').write_text('<h1>Public</h1>')
            (public / '404').mkdir()
            (public / '404/index.html').write_text('Introuvable')
            (public / 'escape.json').symlink_to(root / 'secret.json')
            (public / 'sneak').mkdir()
            (public / 'sneak/index.html').symlink_to(root / 'secret.json')
            (public / 'research').mkdir()
            (public / 'research/corpus-candidate.json').write_text('PRIVATE-SECRET')
            (public / 'assets').mkdir()
            server = ThreadingHTTPServer(('127.0.0.1', 0), functools.partial(server_module.PublicHandler, directory=str(public)))
            threading.Thread(target=server.serve_forever, daemon=True).start()
            origin = f'http://127.0.0.1:{server.server_port}'
            try:
                self.assertIn('Public', urlopen(origin).read().decode())
                for path in ['/research/corpus-candidate.json', '/scripts/build.py', '/backups/', '/escape.json', '/sneak/', '/build-report.json', '/%2e%2e/secret.json', '/assets/', '/.git/config', '/missing/']:
                    with self.assertRaises(HTTPError) as exc:
                        urlopen(origin + path)
                    self.assertEqual(exc.exception.code, 404, path)
                    self.assertNotIn('PRIVATE-SECRET', exc.exception.read().decode())
                (public / '404/index.html').unlink()
                (public / '404/index.html').symlink_to(root / 'secret.json')
                with self.assertRaises(HTTPError) as exc:
                    urlopen(origin + '/missing-again/')
                self.assertNotIn('PRIVATE-SECRET', exc.exception.read().decode())
            finally:
                server.shutdown()
                server.server_close()

    def test_backup_restore_integrity_and_no_overwrite(self):
        ops = load('manage')
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            (root / 'scripts').mkdir()
            (root / 'scripts/a.py').write_text('print("test")')
            (root / 'README.md').write_text('test')
            (root / '.qa').mkdir()
            (root / '.qa/private').write_text('excluded')
            archive = ops.backup(root)
            restored = ops.restore(archive, root / 'restored/copy', root)
            self.assertEqual((restored / 'scripts/a.py').read_text(), 'print("test")')
            self.assertFalse((restored / '.qa').exists())
            with self.assertRaises(ValueError):
                ops.restore(archive, restored, root)
            with self.assertRaises(ValueError):
                ops.restore(archive, root.parent / 'outside', root)

    def test_restore_rejects_traversal_and_tamper(self):
        ops = load('manage')
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            evil = root / 'evil.zip'
            with zipfile.ZipFile(evil, 'w') as z:
                z.writestr('../escape', 'bad')
                z.writestr('MANIFEST.json', '{}')
            with self.assertRaises(ValueError):
                ops.restore(evil, root / 'restored/evil', root)
            self.assertFalse((root / 'restored/evil').exists())
            (root / 'README.md').write_text('safe')
            archive = ops.backup(root)
            with zipfile.ZipFile(archive, 'a') as z:
                z.writestr('extra.txt', 'not in manifest')
            with self.assertRaises(ValueError):
                ops.restore(archive, root / 'restored/tampered', root)
