"""Replay manually annotated source diagrams; no market test or fill claims."""
import argparse,json
from collections import Counter
from decimal import Decimal
from itertools import product
from pathlib import Path
from pullback_topology import PathPoint,PathReference,PullbackTopology

def replay(c):
    r=c['reference'];ref=PathReference(c['id'],r['anchor_at'],Decimal(r['anchor_price']),r['known_at'],c['source'],
        r.get('second_at'),None if r.get('second_price') is None else Decimal(r['second_price']))
    model=PullbackTopology(c['side'],ref,'TEACHER_SCHEMATIC_VERTEX')
    rows=[model.step(PathPoint(p['at'],Decimal(p['price']),c['source'])) for p in c['points']]
    return rows

def evaluate(path):
    doc=json.loads(Path(path).read_text(encoding='utf8'));results=[]
    for c in doc['cases']:
        rows=replay(c);prefix=replay({**c,'points':c['points'][:-1]})
        counts=Counter();anchors=2 if c['reference'].get('second_at') is not None else 1
        # Conservative vertical-coordinate perturbation audit, not probabilities
        # or an exhaustive camera/annotation uncertainty model.
        for signs in product((-2,2),repeat=anchors+len(c['points'])):
            x={**c,'reference':dict(c['reference']),'points':[dict(p) for p in c['points']]}
            x['reference']['anchor_price']=str(Decimal(x['reference']['anchor_price'])+signs[0])
            if anchors==2:x['reference']['second_price']=str(Decimal(x['reference']['second_price'])+signs[1])
            for p,s in zip(x['points'],signs[anchors:]):p['price']=str(Decimal(p['price'])+s)
            counts[replay(x)[-1]['stage']]+=1
        results.append({'id':c['id'],'group':c['group'],'source':c['source'],
            'central_path_stage':rows[-1]['stage'],'prefix_before_confirm_stage':prefix[-1]['stage'],
            'trace':rows,'vertical_uncertainty_corner_counts':dict(counts),'actionable':False})
    return {'domain':doc['scope'],'cases':results,'cases_count':len(results),
        'independent_drawn_object_groups':len({c['group'] for c in doc['cases']}),
        'central_paths_core_confirmed':sum(c['central_path_stage']=='CORE_CONFIRMED' for c in results),
        'prefixes_without_confirmation':sum(c['prefix_before_confirm_stage']!='CORE_CONFIRMED' for c in results),
        'all_source_entries_or_sltp_validated':False,'OHLC_market_backtest':False,'actionable':False,
        'limitations':['manual_pixel_vertices','image_coordinates_not_market_times_or_USD',
            'same_buy_figure_edits_grouped','closed_price_path_is_not_complete_wick_pivot_model',
            'reference_region_and_later_exceptions_not_solved','corner_counts_are_not_probabilities']}

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--cases',type=Path,default=Path(__file__).parent/'docs/S16_SOURCE_PATH_CASES.json')
    p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    if a.cases.resolve()==a.output.resolve() or a.output.exists() and a.cases.samefile(a.output):raise ValueError('output aliases input')
    r=evaluate(a.cases);a.output.write_text(json.dumps(r,ensure_ascii=False,indent=2,default=str)+'\n',encoding='utf8')
    print(json.dumps({'source_paths':r['cases_count'],'groups':r['independent_drawn_object_groups'],
        'core_confirmed':r['central_paths_core_confirmed'],'prefix_waited':r['prefixes_without_confirmation'],
        'uncertainty':[x['vertical_uncertainty_corner_counts'] for x in r['cases']], 'market_test':False}))

if __name__=='__main__':main()
