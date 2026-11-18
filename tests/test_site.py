"""Fixtures purement fictives, jamais livrées dans le corpus public."""
import copy
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


def fixture():
    common = dict(summary='Résumé fictif de test', body='Texte fictif, sans valeur historique.', status='publie', reviewed=True, sourceIds=['s1'])
    return dict(schemaVersion=1, sources=[dict(id='s1', title='Source fictive', url='https://example.org/test', publisher='Test', accessedAt='2026-01-01', evidenceFile='tests/test_site.py')], events=[dict(common, id='e1', slug='evenement-fictif', title='Événement fictif', date=dict(startYear=1900, endYear=1902, label='Vers 1900–1902 (fictif)', precision='circa'), periodId='1884-1916', category='Test', context='Contexte fictif', consequences='Conséquence fictive', certainty='Test seulement', controversies='Non applicable')], people=[], places=[], themes=[], journeys=[])


class SiteTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        spec = importlib.util.spec_from_file_location('site_builder', ROOT / 'scripts/build.py')
        cls.app = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cls.app)

    def test_all_nonpublic_statuses_are_absent(self):
        for status in ('brouillon', 'a-verifier', 'valide', 'publie'):
            for reviewed in (False, True):
                data = fixture()
                data['events'][0].update(status=status, reviewed=reviewed)
                with tempfile.TemporaryDirectory() as d:
                    self.app.build(data, Path(d), ROOT)
                    exists = (Path(d) / 'evenements/evenement-fictif/index.html').exists()
                    self.assertEqual(exists, status == 'publie' and reviewed is True)
                    index = json.loads((Path(d) / 'search-index.json').read_text())
                    self.assertEqual(len(index), int(exists))

    def test_ledger_citation_links_to_declared_number_not_local_position(self):
        data = fixture()
        data['sources'][0]['citationNumber'] = 44
        data['events'][0].update(body='Texte <script>inline[44]</script>.', context=['Contexte [44].'])
        with tempfile.TemporaryDirectory() as d:
            self.app.build(data, Path(d), ROOT)
            page = (Path(d) / 'evenements/evenement-fictif/index.html').read_text()
            self.assertIn('href="#source-44">[44]</a>', page)
            self.assertIn('<li id="source-44"><span class="citation-number">[44]</span>', page)
            self.assertNotIn('>[1]</', page)
            self.assertIn('&lt;script&gt;inline', page)
            self.assertNotIn('<script>inline', page)
            sources_page = (Path(d) / 'sources/index.html').read_text()
            self.assertIn('id="source-44"', sources_page)
            self.assertIn('[44]', sources_page)

    def test_publication_rejects_citations_outside_own_sources(self):
        for field in self.app.CITED_FIELDS:
            for own_number in (None, 1):
                with self.subTest(field=field, own_number=own_number):
                    data = fixture()
                    if own_number is not None:
                        data['sources'][0]['citationNumber'] = own_number
                    data['sources'].append(dict(data['sources'][0], id='other', citationNumber=44))
                    data['events'][0][field] = ['Citation [44].']
                    with self.assertRaisesRegex(ValueError, 'citation.*44'):
                        self.app.validate(data, ROOT)
                    data['events'][0]['reviewed'] = False
                    self.app.validate(data, ROOT)  # Not publishable yet.

    def test_optional_citation_number_never_infers_position(self):
        data = fixture()
        data['events'][0]['body'] = 'Texte [1].'
        with self.assertRaisesRegex(ValueError, 'citation.*1'):
            self.app.validate(data, ROOT)
        data['events'][0]['body'] = 'Texte sans citation.'
        with tempfile.TemporaryDirectory() as d:
            self.app.build(data, Path(d), ROOT)
            page = (Path(d) / 'evenements/evenement-fictif/index.html').read_text()
            self.assertNotIn('citation-number', page)
            self.assertNotIn('[1]', page)

    def test_citation_numbers_positive_unique_strict_integers(self):
        for number in (True, False, 0, -1, 1.5, '44', None):
            with self.subTest(number=number):
                data = fixture()
                data['sources'][0]['citationNumber'] = number
                with self.assertRaisesRegex(ValueError, 'citationNumber'):
                    self.app.validate(data, ROOT)
        data = fixture()
        data['sources'][0]['citationNumber'] = 44
        data['sources'].append(dict(data['sources'][0], id='s2'))
        with self.assertRaisesRegex(ValueError, 'citationNumber'):
            self.app.validate(data, ROOT)

    def test_duplicate_source_ids_within_entry_rejected(self):
        data = fixture()
        data['events'][0]['sourceIds'] = ['s1', 's1']
        with self.assertRaisesRegex(ValueError, 'sourceIds'):
            self.app.validate(data, ROOT)

    def test_documentary_review_notice_and_dates_not_historian_validation(self):
        data = fixture()
        with tempfile.TemporaryDirectory() as d:
            self.app.build(data, Path(d), ROOT)
            page = (Path(d) / 'sources/index.html').read_text()
            self.assertIn('relecture documentaire par des agents', page)
            self.assertIn('pas une validation historienne', page)
            self.assertIn('dates de consultation', page)
            self.assertIn('dates de relecture', page)

    def test_collectives_are_not_individual_biographies(self):
        for field, value in (('category', 'Collectif'), ('entryType', 'collective')):
            with self.subTest(field=field):
                data = fixture()
                data['people'] = [dict(data['events'][0], id='p1', slug='collectif-test', title='Collectif fictif', birthYear=1900, deathYear=2000, **{field: value})]
                with tempfile.TemporaryDirectory() as d:
                    self.app.build(data, Path(d), ROOT)
                    page = (Path(d) / 'personnalites/collectif-test/index.html').read_text()
                    listing = (Path(d) / 'personnalites/index.html').read_text()
                    self.assertIn('Fiche collective', page)
                    self.assertIn('pas une biographie individuelle', page)
                    self.assertIn('Fiche collective', listing)
                    self.assertNotIn('Naissance :', page)
                    self.assertNotIn('Décès :', page)

    def test_editorial_note_rendered_and_escaped_on_each_detail_type(self):
        data = fixture()
        for group in self.app.COLLECTIONS:
            row = dict(data['events'][0], id=group, slug=group, editorialNote='Limite <script>fictive</script>')
            if group == 'places':
                row.update(lat=4, lon=11, modernMap=True)
            data[group] = [row]
        with tempfile.TemporaryDirectory() as d:
            self.app.build(data, Path(d), ROOT)
            for group in self.app.COLLECTIONS:
                page = (Path(d) / self.app.ROUTES[group] / group / 'index.html').read_text()
                self.assertIn('Note éditoriale', page)
                self.assertIn('Limite &lt;script&gt;fictive&lt;/script&gt;', page)
                self.assertNotIn('<script>fictive', page)

    def test_partial_portrait_label_and_incomplete_corpus_notices(self):
        data = fixture()
        data['people'] = [dict(data['events'][0], id='partial', slug='partiel', editorialNote='Portrait partiel : test fictif.')]
        with tempfile.TemporaryDirectory() as d:
            self.app.build(data, Path(d), ROOT)
            for route in ('personnalites', 'personnalites/partiel'):
                page = (Path(d) / route / 'index.html').read_text()
                self.assertIn('Portrait partiel', page)
            for route in ('', 'sources'):
                page = (Path(d) / route / 'index.html').read_text()
                self.assertIn('Corpus incomplet', page)
                self.assertIn('1972–1982 : aucune fiche publiée', page)
                self.assertIn('1 portrait(s) partiel(s)', page)
                self.assertIn('sans validation historienne', page)

    def test_bool_reviewed_not_string(self):
        data = fixture()
        data['events'][0]['reviewed'] = 'true'
        with tempfile.TemporaryDirectory() as d, self.assertRaises(ValueError):
            self.app.build(data, Path(d), ROOT)

    def test_invalid_date_and_coordinates(self):
        data = fixture()
        data['events'][0]['date']['endYear'] = 1800
        with tempfile.TemporaryDirectory() as d, self.assertRaises(ValueError):
            self.app.build(data, Path(d), ROOT)
        data = fixture()
        data['places'] = [dict(data['events'][0], id='place', lat=91, lon=11, modernMap=True)]
        with tempfile.TemporaryDirectory() as d, self.assertRaises(ValueError):
            self.app.build(data, Path(d), ROOT)

    def test_minimal_optional_fields(self):
        data = fixture()
        for field in ('category', 'context', 'consequences', 'certainty', 'controversies'):
            data['events'][0].pop(field, None)
        with tempfile.TemporaryDirectory() as d:
            self.app.build(data, Path(d), ROOT)
            self.assertTrue((Path(d) / 'evenements/evenement-fictif/index.html').exists())

    def test_missing_corpus_never_reads_candidate(self):
        import subprocess
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            (root / 'scripts').mkdir()
            (root / 'research').mkdir()
            import shutil
            shutil.copy(ROOT / 'scripts/build.py', root / 'scripts/build.py')
            shutil.copy(ROOT / 'site_config.json', root / 'site_config.json')
            (root / 'research/corpus-candidate.json').write_text(json.dumps(fixture()))
            result = subprocess.run(['python3', str(root / 'scripts/build.py')], capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(json.loads((root / 'dist/search-index.json').read_text()), [])

    def test_output_must_not_overwrite_research(self):
        import subprocess
        import shutil
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            (root / 'scripts').mkdir()
            shutil.copy(ROOT / 'scripts/build.py', root / 'scripts/build.py')
            shutil.copy(ROOT / 'site_config.json', root / 'site_config.json')
            result = subprocess.run(['python3', str(root / 'scripts/build.py'), '--output', str(root / 'research/should-never-exist')], capture_output=True, text=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertFalse((root / 'research/should-never-exist').exists())

    def test_invalid_reference_fails(self):
        data = fixture()
        data['events'][0]['personIds'] = ['absent']
        with tempfile.TemporaryDirectory() as d, self.assertRaises(ValueError):
            self.app.build(data, Path(d), ROOT)

    def test_duplicate_slug_fails(self):
        data = fixture()
        data['events'].append(dict(data['events'][0], id='e2'))
        with tempfile.TemporaryDirectory() as d, self.assertRaises(ValueError):
            self.app.build(data, Path(d), ROOT)

    def test_published_requires_evidence(self):
        data = fixture()
        data['sources'][0]['evidenceFile'] = 'missing-proof.txt'
        with tempfile.TemporaryDirectory() as d, self.assertRaises(ValueError):
            self.app.build(data, Path(d), ROOT)

    def test_real_pages_and_dates(self):
        data = fixture()
        with tempfile.TemporaryDirectory() as d:
            self.app.build(data, Path(d), ROOT)
            page = (Path(d) / 'evenements/evenement-fictif/index.html').read_text()
            self.assertIn('Vers 1900–1902 (fictif)', page)
            self.assertIn('Contexte fictif', page)
            self.assertIn('Source fictive', page)
            self.assertIn('application/ld+json', page)
            for route in ['', 'frise', 'personnalites', 'themes', 'lieux', 'parcours', 'recherche', 'sources', 'a-propos']:
                self.assertTrue((Path(d) / route / 'index.html').exists(), route)
            self.assertTrue((Path(d) / 'sitemap.xml').exists())

    def test_hidden_relationship_and_journey(self):
        data = fixture()
        data['people'] = [dict(data['events'][0], id='p1', slug='cache', title='NE PAS EXPOSER', reviewed=False)]
        data['events'][0]['personIds'] = ['p1']
        data['journeys'] = [dict(data['events'][0], id='j1', slug='incomplet', steps=[dict(type='person', id='p1')])]
        with tempfile.TemporaryDirectory() as d:
            self.app.build(data, Path(d), ROOT)
            all_text = ''.join(p.read_text() for p in Path(d).rglob('*') if p.suffix in ('.html', '.json', '.xml'))
            self.assertNotIn('NE PAS EXPOSER', all_text)
            self.assertFalse((Path(d) / 'parcours/incomplet/index.html').exists())

    def test_escape_and_evidence_path(self):
        data = fixture()
        data['events'][0]['body'] = '<script>alert(1)</script>'
        with tempfile.TemporaryDirectory() as d:
            self.app.build(data, Path(d), ROOT)
            page = (Path(d) / 'evenements/evenement-fictif/index.html').read_text()
            self.assertIn('&lt;script&gt;', page)
        data['sources'][0]['evidenceFile'] = '../secret'
        with tempfile.TemporaryDirectory() as d, self.assertRaises(ValueError):
            self.app.build(data, Path(d), ROOT)

    def test_publication_gate(self):
        data = fixture()
        data['events'][0]['reviewed'] = False
        with tempfile.TemporaryDirectory() as d:
            self.app.build(data, Path(d), ROOT)
            self.assertFalse((Path(d) / 'evenements/evenement-fictif/index.html').exists())
            self.assertNotIn('Événement fictif', (Path(d) / 'search-index.json').read_text())


if __name__ == '__main__':
    unittest.main()
