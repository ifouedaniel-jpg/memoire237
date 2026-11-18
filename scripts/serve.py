"""Serveur de développement cloisonné : seulement dist, jamais la racine du dépôt."""
import argparse
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path, PurePosixPath
from urllib.parse import unquote, urlsplit

ROOT = Path(__file__).resolve().parents[1]


class PublicHandler(SimpleHTTPRequestHandler):
    # Aucun listing ; liste blanche des sorties réellement générées.
    def allowed(self):
        path = unquote(urlsplit(self.path).path)
        parts = PurePosixPath(path).parts
        if any(p.startswith('.') or p in ('research', 'backups', 'scripts', 'restored', 'tests', 'docs') for p in parts[1:]) or '\\' in path or '\x00' in path:
            return False
        root = Path(self.directory).resolve()
        original = Path(self.translate_path(self.path))
        target = original.resolve()
        if not target.is_relative_to(root) or original.is_symlink() or any(p.is_symlink() for p in original.parents if p != root and p.is_relative_to(root)):
            return False
        if path in ('/search-index.json', '/sitemap.xml', '/robots.txt'):
            return target.is_file()
        if path.startswith('/assets/'):
            return path in ('/assets/style.css', '/assets/app.js', '/assets/icon.svg') and target.is_file()
        # Seuls les documents HTML des routes générées sont publics.
        if target.is_dir():
            index = target / 'index.html'
            return index.is_file() and not index.is_symlink() and index.resolve().is_relative_to(root)
        return target.is_file() and target.suffix == '.html'

    def send_head(self):
        if not self.allowed():
            self.send_response(404)
            self.send_header('Content-Type', 'text/html; charset=utf-8')
            fallback = Path(self.directory) / '404/index.html'
            safe_fallback = fallback.is_file() and not fallback.is_symlink() and not fallback.parent.is_symlink() and fallback.resolve().is_relative_to(Path(self.directory).resolve())
            body = fallback.read_bytes() if safe_fallback else b'Page introuvable'
            self.send_header('Content-Length', str(len(body)))
            self.end_headers()
            import io
            return io.BytesIO(body)
        return super().send_head()

    def list_directory(self, path):
        self.send_error(404)
        return None

    def end_headers(self):
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.send_header('Referrer-Policy', 'no-referrer')
        self.send_header('X-Frame-Options', 'DENY')
        self.send_header('Content-Security-Policy', "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self'; font-src 'self'; connect-src 'self'; object-src 'none'; base-uri 'none'; frame-ancestors 'none'; form-action 'self'")
        super().end_headers()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port', type=int, default=8237)
    parser.add_argument('--token', default='foreground')
    parser.add_argument('--state', type=Path)
    args = parser.parse_args()
    directory = ROOT / 'dist'
    if not (directory / 'build-report.json').is_file():
        raise SystemExit('Build absent : python3 scripts/build.py')
    handler = partial(PublicHandler, directory=str(directory))
    with ThreadingHTTPServer(('127.0.0.1', args.port), handler) as server:
        state = dict(pid=os.getpid(), port=server.server_port, token=args.token, root=str(ROOT))
        if args.state:
            if args.state.resolve() != ROOT / '.run/server.json':
                raise SystemExit('Chemin état interdit')
            args.state.parent.mkdir(exist_ok=True)
            temp = args.state.with_suffix('.new')
            temp.write_text(json.dumps(state))
            temp.replace(args.state)
        print(f'http://127.0.0.1:{server.server_port} — public: {directory}', flush=True)
        server.serve_forever()


if __name__ == '__main__':
    main()
