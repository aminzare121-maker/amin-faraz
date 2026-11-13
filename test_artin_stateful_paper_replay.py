import unittest
from unittest.mock import patch
from artin_stateful_paper_replay import PaperReplayError, replay, execute_sourced_paper_replay


def source(*actions):
    return {'schema':'artin_classroom_trade_actions_result_v1',
            'orders_sent':0,'broker_connected':False,
            'classroom_decision_actions':[
                {'event_id':str(i),'execution':a} for i,a in enumerate(actions)]}


class StatefulPaperReplayTests(unittest.TestCase):
    def setUp(self):
        self.position={'side':'BUY','entry':'4000','current_stop':'3990','lots':'0.01'}

    def test_two_stop_moves_and_trigger_preserve_position_without_fill(self):
        first={'decision':'PAPER_STOP_MOVE_ACCEPTED','order_created':False,
               'old_stop':'3990','new_stop':'3995','lots_before':'0.01','lots_after':'0.01'}
        second={'decision':'MOVE_STOP_TO_ENTRY_PAPER','order_created':False,
                'old_stop':'3995','new_stop':'4000','lots_before':'0.01','lots_after':'0.01'}
        trigger={'decision':'STOP_EXIT_TRIGGER_PAPER_NOT_A_FILL','order_created':False,
                 'stop':'4000','entry':'4000','lots':'0.01'}
        result=replay(source(first,second,trigger),self.position)
        self.assertEqual(result['current_stop'],'4000')
        self.assertTrue(result['stop_triggered_in_model'])
        self.assertFalse(result['position_closed_by_broker'])
        self.assertIsNone(result['realized_pnl'])
        self.assertEqual([x['stop_after'] for x in result['journal']],['3995','4000','4000'])

    def test_reject_stale_stop_without_partial_state(self):
        a={'decision':'PAPER_STOP_MOVE_ACCEPTED','order_created':False,
           'old_stop':'3990','new_stop':'3995','lots_before':'0.01','lots_after':'0.01'}
        with self.assertRaisesRegex(PaperReplayError,'PAPER_POSITION_STATE_MISMATCH'):
            replay(source(a,a),self.position)

    def test_reject_stop_widening(self):
        a={'decision':'PAPER_STOP_MOVE_ACCEPTED','order_created':False,
           'old_stop':'3990','new_stop':'3985','lots_before':'0.01','lots_after':'0.01'}
        with self.assertRaisesRegex(PaperReplayError,'STOP_MUST_TIGHTEN'):
            replay(source(a),self.position)

    def test_source_action_pipeline_updates_paper_position(self):
        action={'decision':'MOVE_STOP_TO_ENTRY_PAPER','order_created':False,
                'old_stop':'3990','new_stop':'4000',
                'lots_before':'0.01','lots_after':'0.01'}
        with patch('artin_classroom_trade_actions.execute',return_value=source(action)) as execute:
            result=execute_sourced_paper_replay({'events':[]},'sources','core',self.position)
        execute.assert_called_once()
        self.assertEqual(result['paper_position']['current_stop'],'4000')
        self.assertEqual(result['orders_sent'],0)
        self.assertFalse(result['broker_connected'])

    def test_reject_stop_action_for_different_position_id(self):
        self.position['position_id']='PAPER-001'
        action={'decision':'MOVE_STOP_TO_ENTRY_PAPER','order_created':False,
                'old_stop':'3990','new_stop':'4000',
                'lots_before':'0.01','lots_after':'0.01'}
        doc=source(action)
        doc['classroom_decision_actions'][0]['position_id']='PAPER-002'
        with self.assertRaisesRegex(PaperReplayError,'PAPER_POSITION_IDENTITY_MISMATCH'):
            replay(doc,self.position)

    def test_reject_order_creation(self):
        with self.assertRaisesRegex(PaperReplayError,'BROKER_ACTION_FORBIDDEN'):
            replay(source({'decision':'NO_TRADE','order_created':True}),self.position)


if __name__=='__main__':
    unittest.main()
