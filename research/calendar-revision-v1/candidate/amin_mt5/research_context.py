"""Bounded public evidence for scenario research; no execution or account data."""
import math
import re
from .sources import SOURCES,plain

from .foresight_catalog import references,review_status
REFERENCES=references()


def execution_context(dashboard):
    from .model import Policy,SymbolSpec,dec
    from dataclasses import asdict
    from .account_profiles import effective_cost_policy
    s=dashboard['snapshot'];a=s['account'];capital=min(dec(dashboard['stage']['active_capital']),dec(a['equity']))
    if a['mode']!='demo' or capital<=0:raise ValueError('Verified DEMO capital required')
    return {'account':a['identity'],'symbol':s['spec']['symbol'],'initial_capital':str(capital),
            'policy':asdict(effective_cost_policy(Policy(**dashboard['active_risk_policy']),
                dashboard.get('account_profile',{}).get('selected'))),'spec':asdict(SymbolSpec(**s['spec']))}


def context_matches(context,snapshot,policy,selected=None):
    from dataclasses import asdict
    from .account_profiles import effective_cost_policy
    return (isinstance(context,dict) and context.get('account')==snapshot.account.identity
            and context.get('symbol')==snapshot.spec.symbol and context.get('policy')==asdict(effective_cost_policy(policy,selected))
            and context.get('spec')==asdict(snapshot.spec))


def public_context(feeds,now):
    known={x.id:x for x in SOURCES};items=[]
    for row in feeds.get('sources',[])[:20]:
        if not isinstance(row,dict) or row.get('id') not in known:continue
        source=known[row['id']];checked=row.get('checked_ms',row.get('received_ms'))
        fresh=type(checked) is int and 0<=now-checked<=180000
        item={'id':source.id,'source_url':source.url,'status':'available' if row.get('status')=='usable_supplemental' and fresh else 'unavailable_or_stale',
              'checked_ms':checked if type(checked) is int else None,'is_complete_calendar':False}
        if item['status']=='available':
            data=row.get('data',{});data=data if isinstance(data,dict) else {}
            records=data.get('records',[])
            if source.id=='world-growth':records=[r for r in records if r.get('geography_code')=='IRN']+[r for r in records if r.get('geography_code')!='IRN']
            item['records']=[{'title':plain(r.get('title',''),220),'url':r.get('url') if isinstance(r.get('url'),str) and len(r['url'])<600 else None,
                              'published_ms':r.get('published_ms') if type(r.get('published_ms')) is int else None}
                             for r in records[:3] if isinstance(r,dict)]
            latest=data.get('latest')
            if isinstance(latest,dict) and type(latest.get('value')) in (int,float) and math.isfinite(latest['value']):
                item['latest']={k:latest.get(k) for k in ('observation_date','value','unit')}
            prior=data.get('previous')
            if isinstance(prior,dict) and type(prior.get('value')) in (int,float) and math.isfinite(prior['value']):
                item['previous']={k:prior.get(k) for k in ('observation_date','value','unit')}
            item['frequency']=data.get('frequency') if data.get('frequency') in ('daily','annual') else None
            item['record_count']=len(data.get('records',[]))
            item['historical_publication_times_verified']=False
        items.append(item)
    return {'generated_ms':now,'public_sources':items,'references':REFERENCES,'calibrated_accuracy_percent':None,
            'all_country_coverage':False,'can_execute':False,'book_full_text_reviewed':False,'foresight_review':review_status(),
            'horizons':{'short_term':'ساعت‌ها تا چند روز؛ هنوز مدل سنجیده‌شدهٔ پیش‌بینی نداریم.',
                        'long_term':'هفته‌ها تا ماه‌ها؛ هنوز مدل سنجیده‌شدهٔ پیش‌بینی نداریم.'}}
