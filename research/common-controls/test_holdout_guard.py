import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import holdout_guard as guard

class SharedExposureTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path=Path(self.tmp.name)/'authority.sqlite'
        guard.provision(self.path)
        p=patch.object(guard,'AUTHORITY',self.path);p.start();self.addCleanup(p.stop)
    def test_renamed_or_repriced_dataset_same_interval_blocked(self):
        guard.seal('a'*64,0,100,80,100)
        with self.assertRaisesRegex(ValueError,'ALREADY_EXPOSED'):guard.seal('b'*64,0,100,80,100)
    def test_overlap_even_when_old_holdout_is_now_training(self):
        guard.seal('a'*64,0,100,80,100)
        with self.assertRaisesRegex(ValueError,'ALREADY_EXPOSED'):guard.seal('c'*64,90,200,180,200)
    def test_new_bank_cannot_reset_shared_journal(self):
        from registry import Registry
        first=Registry(Path(self.tmp.name)/'first.sqlite')
        guard.seal('a'*64,0,100,80,100)
        second=Registry(Path(self.tmp.name)/'second.sqlite')
        with self.assertRaisesRegex(ValueError,'ALREADY_EXPOSED'):guard.seal('d'*64,0,101,81,101)
    def test_adjacent_unseen_period_allowed(self):
        guard.seal('a'*64,0,100,80,100)
        guard.seal('b'*64,100,200,180,200)
    def test_missing_journal_blocks_without_recreating(self):
        self.path.unlink()
        with self.assertRaisesRegex(ValueError,'UNAVAILABLE'):guard.seal('a'*64,0,100,80,100)
        self.assertFalse(self.path.exists())
    def test_cannot_provision_over_existing(self):
        with self.assertRaises(FileExistsError):guard.provision(self.path)
    def test_invalid_interval(self):
        with self.assertRaisesRegex(ValueError,'INVALID'):guard.seal('a'*64,0,100,90,110)
    def test_check_blocks_training_on_exposed_period(self):
        guard.seal('a'*64,0,100,80,100)
        with self.assertRaisesRegex(ValueError,'ALREADY_EXPOSED'):guard.check(90,200)
    def test_racing_seals_only_one_wins(self):
        from concurrent.futures import ThreadPoolExecutor
        def attempt(key):
            try:guard.seal(key*64,0,100,80,100);return 'sealed'
            except ValueError:return 'blocked'
        with ThreadPoolExecutor(max_workers=2) as pool:
            self.assertCountEqual(list(pool.map(attempt,['a','b'])),['sealed','blocked'])

if __name__=='__main__':unittest.main()
