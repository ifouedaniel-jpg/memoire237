"""Unit-test the download verifier without running the live browser crawl."""
import ast
import hashlib
from pathlib import Path
import unittest
from unittest.mock import patch


def load_verifier():
    # qa_domain is a CLI script with top-level network/browser side effects.
    tree = ast.parse(Path(__file__).with_name('qa_domain.py').read_text())
    node = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == 'verify')
    namespace = dict(hashlib=hashlib, BASE='https://saneahair.com')
    exec(compile(ast.Module(body=[node], type_ignores=[]), 'qa_domain.py', 'exec'), namespace)
    return namespace


class DomainIntegrityTests(unittest.TestCase):
    def verify(self, path, raw, expected):
        namespace = load_verifier()
        with patch.dict(namespace, urlopen=lambda *a, **k: Response(raw)):
            return namespace['verify'](dict(path=path, sha256=hashlib.sha256(expected).hexdigest()))

    def test_github_cname_normalization(self):
        for raw in (b'saneahair.com', b'saneahair.com\n'):
            with self.subTest(raw=raw):
                result = self.verify('CNAME', raw, b'saneahair.com\n')
                self.assertEqual(result['sha256'], hashlib.sha256(raw).hexdigest())

    def test_cname_rejects_every_other_content_even_matching_hash(self):
        for raw in (b'www.saneahair.com', b'SANEAHAIR.COM', b'saneahair.com\r\n', b'saneahair.com\n\n', b' saneahair.com', b'saneahair.com ', b'saneahair.com\nevil.com', b'evil.com', b''):
            with self.subTest(raw=raw), self.assertRaises(AssertionError):
                self.verify('CNAME', raw, raw)

    def test_other_files_remain_byte_strict(self):
        for path in ('index.html', 'assets/app.js', 'nested/CNAME'):
            with self.subTest(path=path):
                self.verify(path, b'original\n', b'original\n')
                with self.assertRaises(AssertionError):
                    self.verify(path, b'original', b'original\n')


class Response:
    status = 200

    def __init__(self, raw):
        self.raw = raw

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass

    def read(self):
        return self.raw
