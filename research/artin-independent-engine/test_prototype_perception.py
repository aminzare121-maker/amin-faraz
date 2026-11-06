import unittest
from dataclasses import FrozenInstanceError
from decimal import Decimal as D,localcontext
from prototype_perception import Interval,Sample,EnvelopeModel,leave_one_group_out

def iv(a,b):return Interval(D(a),D(b))
def sample(label,a,b,group,at=10):return Sample(label,{'body_ratio':iv(a,b)},'SYNTHETIC_'+group,at,group)

class PrototypePerceptionTests(unittest.TestCase):
    def test_known_class_is_candidate_never_actionable(self):
        model=EnvelopeModel.fit([sample('A','1','3','g1'),sample('B','6','8','g2')],('body_ratio',),10)
        p=model.predict({'body_ratio':iv('1.5','2.5')},10)
        self.assertEqual(p.label,'A');self.assertTrue(p.candidate_only);self.assertFalse(p.actionable)
        self.assertEqual(model.coverage['A']['groups'],['g1'])

    def test_overlap_boundary_and_uncertainty_abstain(self):
        m=EnvelopeModel.fit([sample('A','1','5','g1'),sample('B','4','8','g2')],('body_ratio',),10)
        for a,b in [('3','4'),('4','4'),('4','6'),('0','2'),('9','10')]:
            self.assertEqual(m.predict({'body_ratio':iv(a,b)},10).status,'UNKNOWN')
        self.assertEqual(m.predict({'body_ratio':iv('2','3')},10).label,'A')

    def test_joint_box_overlap_requires_all_features_and_full_containment(self):
        a=Sample('A',{'x':iv('0','2'),'y':iv('0','2')},'SYNTHETIC_A',1,'ga')
        b=Sample('B',{'x':iv('1','3'),'y':iv('5','7')},'SYNTHETIC_B',1,'gb')
        m=EnvelopeModel.fit([a,b],('x','y'),1)
        self.assertEqual(m.predict({'x':iv('1','2'),'y':iv('0','1')},1).label,'A')
        self.assertEqual(m.predict({'x':iv('1','2.1'),'y':iv('0','1')},1).status,'UNKNOWN')

    def test_group_holdout_excludes_all_edits_and_future_evidence(self):
        rows=[sample('A','1','3','same_figure'),sample('A','1.5','2.5','same_figure'),
              sample('A','1','3','independent'),sample('B','8','9','future',at=20)]
        r=leave_one_group_out(rows,('body_ratio',))
        for x in r['rows']:
            self.assertNotIn(x['held_group'],x['training_groups'])
            if x['held_group']=='same_figure':
                self.assertEqual(x['training_groups'],['independent'])
                self.assertEqual(x['prediction'],'A')
        only=leave_one_group_out(rows[:2],('body_ratio',))
        self.assertEqual(only['unknown'],2);self.assertEqual(only['candidate_predictions'],0)

    def test_immutable_exact_serialization_fingerprint_source_and_schema(self):
        features={'body_ratio':iv('1','3')};s=Sample('A',features,'SYNTHETIC',1,'g')
        features['body_ratio']=iv('9','10');self.assertEqual(s.features['body_ratio'],iv('1','3'))
        with self.assertRaises(TypeError):s.features['body_ratio']=iv('0','1')
        m=EnvelopeModel.fit([s],('body_ratio',),1)
        with self.assertRaises(FrozenInstanceError):m.trained_at=2
        with localcontext() as ctx:
            ctx.prec=2
            self.assertEqual(m.fingerprint,EnvelopeModel.fit([Sample('A',{'body_ratio':iv('1.000','3.00')},'SYNTHETIC',1,'g')],('body_ratio',),1).fingerprint)
        changed=EnvelopeModel.fit([Sample('A',s.features,'OTHER_SOURCE',1,'g')],('body_ratio',),1)
        self.assertNotEqual(m.fingerprint,changed.fingerprint)
        precise=EnvelopeModel.fit([Sample('A',{'body_ratio':iv('1.0000000000000000000000000001','3')},'SYNTHETIC',1,'g')],('body_ratio',),1)
        self.assertNotEqual(m.fingerprint,precise.fingerprint)

    def test_invalid_finite_inputs_schema_and_time(self):
        for a,b in [(float('1'),D(2)),(D('NaN'),D(2)),(D(3),D(2)),(D(1),D('Infinity'))]:
            with self.assertRaises(ValueError):Interval(a,b)
        s=sample('A','1','3','g',20)
        with self.assertRaises(ValueError):EnvelopeModel.fit([s],('body_ratio',),19)
        m=EnvelopeModel.fit([s],('body_ratio',),20)
        self.assertEqual(m.predict({'body_ratio':iv('1','2')},19).status,'UNKNOWN')
        with self.assertRaises(ValueError):m.predict({'other':iv('1','2')},20)
        with self.assertRaises(ValueError):EnvelopeModel.fit([s],('other',),20)

if __name__=='__main__':unittest.main()
