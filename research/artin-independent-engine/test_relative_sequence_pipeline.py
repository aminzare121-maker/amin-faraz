import json,unittest
from decimal import Decimal as D
from context_inputs import Context
from raw_geometry import Candle
from raw_pipeline import RawPipeline

def bar(t,o,c):
    a,b=D(o),D(c)
    return Candle(t,t+900,a,max(a,b),min(a,b),b)

class SequencePipelineTests(unittest.TestCase):
    def test_explicit_selection_produces_exact_serializable_measurement_not_strength(self):
        ctx=Context(0,3600,0,{'sequence_start_opened_at':0},'SYNTHETIC_SEQUENCE_SELECTION')
        p=RawPipeline('SEQUENCE_PROBE',('BREAK_STRONG',),900,'a'*64,[ctx])
        p.step(bar(0,'100','102'))
        result=p.step(bar(900,'102','105'))
        metric=result['relative_sequence_measurement']
        self.assertEqual(metric['target_body_to_context_max_body'],{'numerator':3,'denominator':2})
        self.assertEqual(metric['parent_open_times'],(0,900))
        self.assertFalse(metric['actionable']);self.assertIsNone(metric['strength_label'])
        self.assertTrue(all('break_strength' in d['missing_dependencies'] for d in result['decisions']))
        json.dumps(result,default=str)
    def test_mid_target_selection_is_not_retroactive(self):
        ctx=Context(0,3600,901,{'sequence_start_opened_at':0},'LATE_SYNTHETIC_SELECTION')
        p=RawPipeline('LATE_SEQUENCE_PROBE',('BREAK_STRONG',),900,'a'*64,[ctx])
        p.step(bar(0,'100','102'))
        metric=p.step(bar(900,'102','105'))['relative_sequence_measurement']
        self.assertEqual(metric['status'],'UNKNOWN')
        self.assertEqual(metric['reason'],'SEQUENCE_SELECTION_NOT_KNOWN_BEFORE_TARGET')

if __name__=='__main__':unittest.main()
