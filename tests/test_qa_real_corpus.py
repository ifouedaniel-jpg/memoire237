"""Unit checks for QA mechanics; these do not claim a real-corpus browser audit."""
import importlib.util
from pathlib import Path
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class RealCorpusQATest(unittest.TestCase):
    def setUp(self):
        spec = importlib.util.spec_from_file_location('real_qa', ROOT / 'tests/qa_real_corpus.py')
        self.qa = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.qa)

    def test_fragment_target_checked_not_only_http_status(self):
        page = '<main id="contenu"><a href="#source-44">[44]</a><li id="source-44">S</li></main>'
        scan = self.qa.HTMLScan(page)
        self.assertEqual(scan.hrefs, ['#source-44'])
        self.assertIn('source-44', scan.ids)
        self.qa.check_fragment(page, 'source-44')
        with self.assertRaisesRegex(AssertionError, 'source-1'):
            self.qa.check_fragment(page, 'source-1')
        with self.assertRaisesRegex(AssertionError, 'unique'):
            self.qa.check_fragment(page + '<div id="source-44"></div>', 'source-44')

    def test_normalized_search_matches_accents_and_ligatures(self):
        self.assertEqual(self.qa.normalize('RÉUNIFICATION Œ Æ'), 'reunification oe ae')

    def test_absent_final_is_skipped_without_importing_playwright(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / 'research').mkdir()
            (root / 'research/corpus-candidate.json').write_text('NOT A FINAL CORPUS')
            report = self.qa.run(root)
            self.assertEqual(report['status'], 'skipped')
            self.assertEqual(report['reason'], 'research/corpus.json absent')
            self.assertFalse((root / 'dist').exists())


if __name__ == '__main__':
    unittest.main()
