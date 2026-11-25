import json
from pathlib import Path
import tempfile
import sys
import sqlite3
import time
import unittest
from unittest.mock import patch

from app.document_index import DocumentIndex, parse_manifest, usable_page, run_bounded, extract_pdf, prepare_collection


class DocumentIndexTests(unittest.TestCase):
    def test_manifest_is_data_and_paths_stay_inside_archive(self):
        root = '/content/medicine_2024-08/'
        docs = parse_manifest("var DATABASE = [{'ti':'First aid','fp':['Aid (1).pdf']}];", root)
        self.assertEqual(docs[0]['link'], root + 'Aid%20%281%29.pdf')
        for value in ('../escape.pdf', '%2e%2e/escape.pdf', 'https://bad.test/a.pdf', '/a.pdf', 'a%252fescape.pdf'):
            with self.subTest(value=value), self.assertRaises(ValueError):
                parse_manifest('var DATABASE = ' + json.dumps([{'ti':'Bad','fp':[value]}]), root)
        with self.assertRaises(ValueError):
            parse_manifest("var DATABASE = makeDocuments();", root)
        with self.assertRaises(ValueError):
            parse_manifest("var DATABASE = []; alert('run');", root)

    def test_atomic_replacement_selection_and_archive_update(self):
        with tempfile.TemporaryDirectory() as directory:
            index = DocumentIndex(directory)
            book = {'name':'medicine','archive_uuid':'v1','served_name':'medicine_1'}
            row = {'text':'Emergency wound dressing instructions and clean bandages.', 'title':'First aid', 'link':'/content/medicine_1/aid.pdf#page=2', 'page':2, 'document_hash':'abc'}
            index.replace(book, [row], {'pages':1,'excluded_pages':[]})
            hits = index.search(['wound dressing'], [book])
            self.assertEqual(len(hits), 1)
            self.assertEqual(hits[0]['page'], 2)
            self.assertEqual(index.search(['wound'], []), [])
            self.assertEqual(index.search(['wound'], [dict(book, archive_uuid='v2')]), [])
            def interrupted():
                yield dict(row, text='Replacement incomplete')
                raise InterruptedError('cancelled')
            with self.assertRaises(InterruptedError):
                index.replace(book, interrupted(), {})
            self.assertEqual(len(index.search(['wound'], [book])), 1)
            self.assertEqual(index.status(book)['state'], 'indexed')
            self.assertFalse(list(Path(directory).glob('*.tmp')))

    def test_scans_garbled_text_and_broken_tables_are_not_evidence(self):
        self.assertFalse(usable_page(''))
        self.assertFalse(usable_page('\ufffd' * 100))
        self.assertFalse(usable_page('Dose       Adult      Child\nDrug       10         3'))
        self.assertTrue(usable_page('This is a complete readable sentence about wound dressing and clean bandages.'))

    def test_partial_coverage_is_explicit_and_sql_is_not_executed(self):
        with tempfile.TemporaryDirectory() as directory:
            index = DocumentIndex(directory)
            book = {'name':'medicine','archive_uuid':'v1','served_name':'medicine_1'}
            index.replace(book, [], {'pages':2,'excluded_pages':[1,2]})
            self.assertEqual(index.status(book)['state'], 'browse_only')
            self.assertEqual(index.search(['" OR 1=1; DROP TABLE passages;'], [book]), [])

    def test_extractor_process_limits_and_cancellation(self):
        with self.assertRaises(TimeoutError):
            run_bounded([sys.executable, '-c', 'import time; time.sleep(10)'], timeout=.05)
        with self.assertRaises(ValueError):
            run_bounded([sys.executable, '-c', 'print("x" * 10000)'], max_bytes=10)
        with self.assertRaises(InterruptedError):
            run_bounded([sys.executable, '-c', 'print("unused")'], cancelled=lambda: True)

    def test_pdf_pages_keep_provenance_and_report_unreadable_pages(self):
        page = b'This is a complete readable sentence about wound dressing and clean bandages.'
        with tempfile.TemporaryDirectory() as directory:
            pdf = Path(directory) / 'aid.pdf'
            pdf.write_bytes(b'%PDF-1.4\nsynthetic fixture')
            doc = {'title':'First aid','link':'/content/medicine/aid.pdf'}
            with patch('app.document_index.run_bounded', side_effect=[b'Pages: 2\n', page + b'\f\f']):
                rows, coverage = extract_pdf(pdf, doc, '/tmp/pdftotext')
            self.assertEqual(rows[0]['page'], 1)
            self.assertEqual(rows[0]['link'], doc['link'] + '#page=1')
            self.assertEqual(coverage['excluded_pages'], [2])
            with patch('app.document_index.run_bounded', return_value=b'Pages: 2001\n'):
                with self.assertRaises(ValueError):
                    extract_pdf(pdf, doc, '/tmp/pdftotext')

    def test_collection_uses_manifest_files_prefix_and_reports_failures(self):
        book = {'name':'medicine','archive_uuid':'1','served_name':'medicine_1','content_url':'/content/medicine_1'}
        visited = []
        def fetch(link, **limits):
            visited.append(link)
            if link.endswith('database.js'):
                return b"var DATABASE = [{'ti':'First aid','fp':['aid.pdf']}];"
            raise TimeoutError('unavailable')
        with tempfile.TemporaryDirectory() as directory:
            coverage = prepare_collection(book, DocumentIndex(directory), '/tmp/pdftotext', fetch)
            self.assertEqual(visited[-1], '/content/medicine_1/files/aid.pdf')
            self.assertEqual(coverage['failures'][0]['reason'], 'TimeoutError')

    def test_late_cancellation_preserves_previous_index(self):
        with tempfile.TemporaryDirectory() as directory:
            index = DocumentIndex(directory)
            book = {'name':'medicine','archive_uuid':'1','served_name':'medicine_1'}
            row = {'text':'Original evidence stays available for inspection.', 'title':'Original','link':'/content/medicine_1/a.pdf','page':1}
            index.replace(book, [row], {})
            cancelled = [False]
            def rows():
                yield dict(row, text='New incomplete evidence')
                cancelled[0] = True
            with self.assertRaises(InterruptedError):
                index.replace(book, rows(), {}, cancelled=lambda: cancelled[0])
            self.assertEqual(len(index.search(['Original evidence'], [book])), 1)

    def test_identity_corruption_and_explicit_cleanup(self):
        with tempfile.TemporaryDirectory() as directory:
            index = DocumentIndex(directory)
            book = {'name':'medicine','archive_uuid':'1','served_name':'medicine_1'}
            self.assertEqual(index.status({'name':'medicine','served_name':'medicine_1'})['state'], 'identity_invalid')
            index.replace(book, [], {})
            with sqlite3.connect(index._path(book)) as db:
                db.execute('UPDATE metadata SET value=? WHERE key=?', ('[]','coverage'))
            self.assertEqual(index.status(book)['reason'], 'index_invalid')
            note = Path(directory) / 'personal-notes.md'
            note.write_text('preserve my knowledge')
            self.assertEqual(index.cleanup([]), 1)
            self.assertEqual(note.read_text(), 'preserve my knowledge')

    def test_unchanged_document_reuses_extracted_pages(self):
        with tempfile.TemporaryDirectory() as directory:
            index = DocumentIndex(directory)
            book = {'name':'medicine','archive_uuid':'1','served_name':'medicine_1','content_url':'/content/medicine_1'}
            fetch = lambda link, **kw: b"var DATABASE = [{'ti':'Aid','fp':['a.pdf']}];" if link.endswith('js') else b'%PDF-1.4 fake'
            row = {'text':'An unchanged readable instruction remains searchable.', 'title':'Aid', 'link':'/content/medicine_1/files/a.pdf#page=1','page':1}
            with patch('app.document_index.extract_pdf', return_value=([row], {'pages':1,'excluded_pages':[]})) as extract:
                prepare_collection(book,index,'/tmp/pdftotext',fetch)
                first_id = index.search(['unchanged'], [book])[0]['id']
                prepare_collection(book,index,'/tmp/pdftotext',fetch)
                self.assertEqual(index.search(['unchanged'], [book])[0]['id'], first_id)
            self.assertEqual(extract.call_count, 1)

    def test_page_validation_cannot_overrun_document_deadline(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'a.pdf'; path.write_bytes(b'%PDF-1.4 fixture')
            with patch('app.document_index.run_bounded', side_effect=[b'Pages: 1\n',b'Readable page\f']), patch('app.document_index.usable_page', side_effect=lambda text: (time.sleep(.06) or True)):
                with self.assertRaises(TimeoutError):
                    extract_pdf(path,{'title':'Aid','link':'/a.pdf'},'/tmp/pdftotext',timeout=.03)


if __name__ == '__main__':
    unittest.main()
