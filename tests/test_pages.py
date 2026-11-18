"""Sous-chemin GitHub Pages, sans changement du corpus ni des preuves."""
import json
from pathlib import Path
import re
import tempfile
import unittest
from test_site import fixture, ROOT
import test_site


class PagesTest(unittest.TestCase):
    def test_subpath_urls_assets_search_and_canonical(self):
        test_site.SiteTest.setUpClass()
        data = fixture()
        data['sources'][0]['citationNumber'] = 44
        data['events'][0]['body'] = 'Citation [44].'
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp)
            test_site.SiteTest.app.build(data, out, ROOT, base_url='https://example.org/memoire237')
            for file in out.rglob('*.html'):
                html = file.read_text()
                for url in re.findall(r'(?:href|src)="(/[^\"]*)"', html):
                    self.assertTrue(url.startswith('/memoire237/'), (file, url))
                self.assertIn('https://example.org/memoire237/', html)
            detail = (out / 'evenements/evenement-fictif/index.html').read_text()
            self.assertIn('href="#source-44"', detail)
            rows = json.loads((out / 'search-index.json').read_text())
            self.assertEqual(rows[0]['url'], '/memoire237/evenements/evenement-fictif/')
            self.assertIn('/memoire237/evenements/evenement-fictif/', (out / 'sitemap.xml').read_text())
            self.assertTrue((out / '404.html').is_file())
            self.assertTrue((out / '.nojekyll').is_file())
            self.assertNotIn("fetch('/search-index.json'", (out / 'assets/app.js').read_text())


if __name__ == '__main__':
    unittest.main()
