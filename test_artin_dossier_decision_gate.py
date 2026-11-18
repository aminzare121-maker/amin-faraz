"""Regression tests for the private dossier -> motor decision boundary."""
import unittest
from artin_dossier_decision_gate import inspect_dossier
from artin_13_teacher_acceptance_matrix import EXPECTED_ROUTES


def fixture():
    return {'citations': 24, 'routes': [
        {'route_id': route, 'citation_intervals': [
            {'index': i + 1, 'session': 21, 'start': i * 10.,
             'end': i * 10. + 1.}
            for i in range(24) if i % 13 == j]}
        for j, route in enumerate(sorted(EXPECTED_ROUTES))]}


class DossierDecisionGateTests(unittest.TestCase):
    def test_complete_dossier_still_blocks(self):
        result = inspect_dossier(fixture())
        self.assertEqual(result['reason'], 'ORIGINAL_TEACHER_AV_REPLAY_NOT_CERTIFIED')
        self.assertFalse(result['executable'])
        self.assertFalse(result['trade_authorized'])
        self.assertEqual(result['approved_rule_outcomes'], [])

    def test_source_session_index_must_match_cited_sessions(self):
        d = fixture()
        d['routes'][0]['source_sessions'] = [22]
        self.assertEqual(inspect_dossier(d)['reason'], 'SOURCE_SESSION_INDEX_MISMATCH')
        d['routes'][0]['source_sessions'] = [21]
        self.assertEqual(inspect_dossier(d)['reason'], 'ORIGINAL_TEACHER_AV_REPLAY_NOT_CERTIFIED')
        d['routes'][0]['source_sessions'] = [21, 21]
        self.assertEqual(inspect_dossier(d)['reason'], 'INVALID_SOURCE_SESSION_INDEX')

    def test_missing_citation_fails(self):
        d = fixture()
        d['routes'][0]['citation_intervals'].pop()
        self.assertEqual(inspect_dossier(d)['reason'], 'INCOMPLETE_CITATION_COVERAGE')

    def test_duplicate_interval_fails(self):
        d = fixture()
        d['routes'][1]['citation_intervals'][0]['index'] = 1
        self.assertEqual(inspect_dossier(d)['reason'], 'INVALID_SOURCE_INTERVAL')

    def test_fake_certification_does_not_authorize(self):
        d = fixture()
        d['semantics_independently_approved'] = 13
        d['trading_authorized'] = True
        self.assertFalse(inspect_dossier(d)['trade_authorized'])

    def test_unhashable_route_identifier_blocks_without_crashing(self):
        for invalid in ([], {'route': 'REVERSAL_THREE'}, None, 7):
            d = fixture()
            d['routes'][0]['route_id'] = invalid
            result = inspect_dossier(d)
            self.assertEqual(result['reason'], 'INVALID_PRIVATE_ROUTE_SET')
            self.assertFalse(result['trade_authorized'])

    def test_malformed_session_evidence_never_crashes_motor(self):
        for bad in ([], {'unexpected': 21}, None, '21', 21.0):
            d = fixture()
            d['routes'][0]['source_sessions'] = [21]
            d['routes'][0]['citation_intervals'][0]['session'] = bad
            result = inspect_dossier(d)
            self.assertEqual(result['reason'], 'INVALID_SOURCE_INTERVAL')
            self.assertFalse(result['executable'])
            self.assertFalse(result['trade_authorized'])

    def test_malformed_interval_rejected_before_session_comparison(self):
        d = fixture()
        d['routes'][0]['source_sessions'] = [21]
        d['routes'][0]['citation_intervals'][0] = ['invalid']
        result = inspect_dossier(d)
        self.assertEqual(result['reason'], 'INVALID_SOURCE_INTERVAL')
        self.assertFalse(result['trade_authorized'])

    def test_out_of_range_citation_blocks(self):
        d = fixture()
        d['routes'][0]['citation_intervals'][0]['index'] = 25
        self.assertEqual(inspect_dossier(d)['reason'], 'INVALID_SOURCE_INTERVAL')

    def test_invalid_time_fails(self):
        d = fixture()
        d['routes'][0]['citation_intervals'][0]['end'] = float('nan')
        self.assertEqual(inspect_dossier(d)['reason'], 'INVALID_SOURCE_INTERVAL')


if __name__ == '__main__':
    unittest.main()
