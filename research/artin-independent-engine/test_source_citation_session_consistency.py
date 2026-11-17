"""Source-index regression only; not teacher-semantic certification."""
import unittest
from entry_engine import SOURCES

class SourceCitationSessionConsistency(unittest.TestCase):
    def test_pause_case_points_to_private_dossier_citation_one(self):
        # Private dossier citation 1: session 21, 1888.10..1952.66.
        # The route's legacy S22 identifier is preserved for compatibility.
        self.assertEqual(SOURCES['STOPPUNCH_S22_SELL_CONFIRMED_PAUSE'],
                         ((21, 1888.1, 1952.66),))

if __name__ == '__main__':
    unittest.main()
