"""Evaluate a source-labelled drawing corpus; no trading or market inference."""
import argparse,json
from dataclasses import asdict
from decimal import Decimal
from pathlib import Path
from prototype_perception import Interval,Sample,EnvelopeModel,leave_one_group_out

def evaluate(path):
    d=json.loads(Path(path).read_text(encoding='utf-8-sig'))
    if d['domain']!='TEACHER_DRAWING_GEOMETRY_ONLY':raise ValueError('drawing domain required')
    samples=[Sample(x['label'],{k:Interval(Decimal(v['low']),Decimal(v['high'])) for k,v in x['features'].items()},
                    x['source'],x['known_at'],x['group']) for x in d['samples']]
    schema=tuple(d['feature_schema']);model=EnvelopeModel.fit(samples,schema,trained_at=2)
    training=[{'source':s.source,'expected':s.label,**asdict(model.predict(s.features,at=2))} for s in samples]
    holdout=leave_one_group_out(samples,schema)
    return {'domain':d['domain'],'clock_basis':d['clock_basis'],'model':model.serialize(),
        'fingerprint':model.fingerprint,'training_reconstruction':training,
        'training_same_label':sum(r['label']==r['expected'] for r in training),
        'group_holdout':holdout,'generalization_verified':False,'market_ready':False,
        'actionable':False,'candidate_only':True,
        'limitations':['manual_pixel_annotations','ASR_assisted_episode_labels_not_new_audio',
            'relative_sequence_scale_not_measured','few_independent_drawn_objects',
            'not_market_OHLC_or_teacher_complete_trades','envelope_can_bridge_unobserved_holes']}

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--casefile',type=Path,default=Path(__file__).parent/'docs/TEACHER_DRAWING_FEATURE_CASES.json')
    p.add_argument('--output',type=Path,required=True)
    a=p.parse_args()
    if a.casefile.resolve()==a.output.resolve() or a.output.exists() and a.casefile.samefile(a.output):raise ValueError('output aliases input')
    result=evaluate(a.casefile);a.output.write_text(json.dumps(result,indent=2)+'\n',encoding='utf8')
    print(json.dumps({'training_samples':len(result['training_reconstruction']),
        'training_reconstructed':result['training_same_label'],
        'holdout_correct':result['group_holdout']['correct_candidates'],
        'holdout_unknown':result['group_holdout']['unknown'],'market_ready':False}))

if __name__=='__main__':main()
