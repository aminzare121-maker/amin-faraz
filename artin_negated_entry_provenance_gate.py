"""Public, fail-closed gate for Artin ASR negative-entry sources.
Private input data remains in /بهروز. No trading approval is produced.
"""
from collections import defaultdict

NEGATIONS=('نمی کنیم','نکنید','نکنم','نمی‌کنیم','نکن')

def audit(citation_doc,polarity_doc):
    observed=defaultdict(list)
    for citation in citation_doc['citations']:
        for excerpt in citation['excerpts']:
            observed[(citation['session'],excerpt['asr_segment_id'])].append((citation['route_id'],excerpt))
    cases={}
    for route in polarity_doc['routes']:
        for item in route['cases']:
            if item['polarity_triage']!='POSSIBLE_NEGATED_ENTRY': continue
            key=(item['session'],item['segment_id'])
            matches=observed.get(key,[])
            if not matches:raise ValueError('source missing')
            route_matches=[e for route_id,e in matches if route_id==route['route_id']]
            if not route_matches:raise ValueError('route identity mismatch')
            if not any(abs(e['start']-item['start_seconds'])<1e-6 for e in route_matches):
                raise ValueError('timestamp mismatch')
            variants={(e['text_unverified'],e['original_audio_sha256'],e['start'],e['end']) for _,e in matches}
            if len(variants)!=1:raise ValueError('conflicting source versions')
            text,sha,start,end=next(iter(variants))
            if not any(neg in text for neg in NEGATIONS):raise ValueError('negation unsupported')
            if key not in cases:
                cases[key]={'session':key[0],'segment_id':key[1],'start_seconds':start,
                'end_seconds':end,'text_unverified':text,'audio_source_sha256':sha,
                'assigned_routes':set(),'teacher_semantics_verified':False,'action':'NO_TRADE'}
            cases[key]['assigned_routes'].add(route['route_id'])
    values=[]
    for c in sorted(cases.values(),key=lambda x:(x['session'],x['start_seconds'])):
        c['assigned_routes']=sorted(c['assigned_routes'])
        values.append(c)
    return {'schema':'artin_negative_entry_gate_v1','unique_cases':len(values),
        'cases':values,'teacher_semantics_verified':False,'orders_authorized':0}
