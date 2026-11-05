import tempfile,unittest
from pathlib import Path
from fair_search import find_files

class FairSearchTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.roots=[Path(self.tmp.name)/str(i) for i in range(2)]
        for root in self.roots:root.mkdir()
        for i in range(5):(self.roots[0]/f'unrelated{i}.txt').write_text('fixture')
        (self.roots[1]/'needle.txt').write_text('fixture')
    def test_later_root_not_starved(self):
        result=find_files('needle.txt',self.roots,max_visits=2)
        self.assertEqual(len(result['matches']),1);self.assertEqual(result['scanned'],2)
    def test_reversal_same_target(self):
        self.assertEqual(find_files('needle.txt',self.roots,max_visits=2)['matches'],find_files('needle.txt',self.roots[::-1],max_visits=2)['matches'])
    def test_excluded_directory(self):
        hidden=self.roots[1]/'node_modules';hidden.mkdir();(hidden/'secret.txt').write_text('private')
        self.assertFalse(find_files('secret.txt',self.roots)['matches'])
    def test_name_search_never_extracts(self):
        def explode(path):raise AssertionError('No extraction for filename search')
        self.assertTrue(find_files('needle.txt',self.roots,excerpt=explode)['matches'])
    def test_missing_root_and_result_cap(self):
        result=find_files('.txt',[Path(self.tmp.name)/'missing']+self.roots,max_results=1)
        self.assertEqual(len(result['matches']),1)
    def test_empty_query_no_scan(self):self.assertEqual(find_files('a',self.roots)['scanned'],0)

if __name__=='__main__':unittest.main()
