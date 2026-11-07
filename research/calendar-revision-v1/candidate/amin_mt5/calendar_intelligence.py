"""Versioned evidence and conditional reasoning for the EXISTING research panel.

No network, account, model fitting, probability or order capability. Curated rules
are hypotheses, not discovered/validated causal laws. Recompute from live evidence
on every revision, withdrawal, expiry or regime change, never accumulate scores.
"""
import copy
import hashlib
import json
import os
from pathlib import Path
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from urllib.parse import urlsplit

MODEL_VERSION='calendar-conditional-v1'

def digest(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True,ensure_ascii=False,separators=(',',':'),allow_nan=False).encode()).hexdigest()

def stamp(value):
    if not isinstance(value,str): raise ValueError('TIME_STRING_REQUIRED')
    dt=datetime.fromisoformat(value.replace('Z','+00:00'))
    if dt.tzinfo is None: raise ValueError('TIMEZONE_REQUIRED')
    return int(dt.astimezone(timezone.utc).timestamp()*1000)

def number(value):
    if value is None or value=='': return None
    if isinstance(value,bool): raise ValueError('BOOLEAN_NOT_NUMBER')
    text=str(value).translate(str.maketrans('۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩','01234567890123456789'))
    text=text.replace('٫','.').replace('−','-').strip()
    # Reject ambiguous separators, rather than silently changing magnitude.
    if ',' in text or '٬' in text: raise ValueError('AMBIGUOUS_GROUPING')
    v=Decimal(text)
    if not v.is_finite(): raise ValueError('FINITE_NUMBER_REQUIRED')
    return v

def normalize(record,now_ms,registry):
    r=copy.deepcopy(record); reasons=[]
    required=('id','origin_id','metric','period','unit','publisher','source_url','event_at','published_at','observed_at','checked_at','raw_sha256')
    for key in required:
        if not isinstance(r.get(key),str) or not r[key]: reasons.append('MISSING_'+key)
    times={}
    for key in ('event_at','published_at','observed_at','checked_at'):
        try: times[key]=stamp(r[key])
        except (ValueError,KeyError,TypeError): reasons.append('INVALID_'+key)
    source=registry.get(r.get('publisher'),{})
    url=urlsplit(str(r.get('source_url','')))
    if url.scheme!='https' or url.hostname!=source.get('host') or url.username or url.password or url.port not in (None,443): reasons.append('SOURCE_NOT_REGISTERED')
    if source.get('rights')!='ALLOWED' or not source.get('evidence_id'): reasons.append('SOURCE_RIGHTS_UNKNOWN')
    if r.get('origin_id')!=source.get('origin_id'): reasons.append('ORIGIN_UNVERIFIED')
    raw_hash=r.get('raw_sha256','')
    if len(raw_hash)!=64 or any(c not in '0123456789abcdef' for c in raw_hash): reasons.append('RAW_HASH_MISSING')
    # Trusted collector must verify bytes; a record-level boolean is not evidence.
    if raw_hash not in source.get('verified_receipts',[]): reasons.append('RECEIPT_NOT_VERIFIED')
    if len(times)==4:
        if not times['event_at']<=times['published_at']<=times['observed_at']<=times['checked_at']<=now_ms: reasons.append('TIME_ORDER_OR_FUTURE')
        if now_ms-times['checked_at']>source.get('max_check_age_ms',3600000): reasons.append('STALE_CHECK')
        if now_ms-times['published_at']>source.get('max_fact_age_ms',86400000): reasons.append('STALE_FACT')
    vals={}
    for key in ('actual','forecast','previous'):
        try: vals[key]=number(r.get(key))
        except (InvalidOperation,ValueError): vals[key]=None; reasons.append('INVALID_'+key)
    if vals['actual'] is None: reasons.append('NO_ACTUAL')
    forecast_ok=False
    if vals['forecast'] is not None:
        try:
            forecast_ok=(stamp(r['forecast_asof'])<times['event_at'] and r.get('forecast_evidence_id') in source.get('forecast_receipts',[]))
        except (ValueError,KeyError,TypeError): pass
        if not forecast_ok: reasons.append('FORECAST_UNVERIFIED_OR_LATE')
    revision=r.get('revision',0)
    if type(revision) is not int or revision<0: reasons.append('REVISION_INVALID')
    surprise=vals['actual']-vals['forecast'] if vals['actual'] is not None and forecast_ok else None
    change=vals['actual']-vals['previous'] if vals['actual'] is not None and vals['previous'] is not None else None
    r.update(status='VERIFIED_CURRENT' if not reasons else 'STALE' if any(x.startswith('STALE') for x in reasons) else 'UNKNOWN',
             reasons=reasons,revision=revision,source_independent_group=source.get('origin_id'),
             numbers={**{k:str(v) if v is not None else None for k,v in vals.items()},
                      'surprise':str(surprise) if surprise is not None else None,'change':str(change) if change is not None else None},
             published_ms=times.get('published_at'),available_ms=times.get('observed_at'))
    return r

class Ledger:
    """Append-only local event journal. Retractions are tombstones, not erasures."""
    def __init__(self, entries=None):
        self.entries=[]
        for entry in entries or []:
            expected=digest({k:v for k,v in entry.items() if k!='hash'})
            if entry.get('hash')!=expected or entry.get('previous_hash')!=(self.entries[-1]['hash'] if self.entries else None): raise ValueError('JOURNAL_TAMPER')
            self.entries.append(copy.deepcopy(entry))
    def append(self,record,received_ms,action='UPSERT'):
        if action not in ('UPSERT','RETRACT'): raise ValueError('ACTION')
        if type(received_ms) is not int or (self.entries and received_ms<self.entries[-1]['received_ms']): raise ValueError('JOURNAL_TIME')
        if not isinstance(record,dict) or not all(isinstance(record.get(k),str) and record[k] for k in ('id','origin_id','metric','period','unit')): raise ValueError('IDENTITY')
        if type(record.get('revision',0)) is not int or record.get('revision',0)<0: raise ValueError('REVISION')
        payload={'action':action,'record':copy.deepcopy(record)}
        if self.entries and any(e['action']==action and e['record']==record for e in self.entries): return False
        identity=tuple(record[k] for k in ('origin_id','id','metric','period','unit'))
        prior=[e for e in self.entries if tuple(e['record'][k] for k in ('origin_id','id','metric','period','unit'))==identity]
        if prior and record.get('revision',0)<=max(e['record'].get('revision',0) for e in prior): raise ValueError('REVISION_NOT_INCREASING')
        entry={**payload,'received_ms':received_ms,'previous_hash':self.entries[-1]['hash'] if self.entries else None}
        entry['hash']=digest(entry);self.entries.append(entry);return True
    def active(self,now_ms):
        current={}
        for e in self.entries:
            if e['received_ms']>now_ms: continue
            r=e['record'];key=tuple(r[k] for k in ('origin_id','id','metric','period','unit'))
            current[key]=e
        return [copy.deepcopy(e['record']) for e in current.values() if e['action']=='UPSERT']
    def export(self): return copy.deepcopy(self.entries)
    def save(self,path):
        path=Path(path);temporary=path.with_suffix(path.suffix+'.tmp')
        with temporary.open('w',encoding='utf-8') as f:
            json.dump(self.entries,f,ensure_ascii=False,allow_nan=False);f.flush();os.fsync(f.fileno())
        os.replace(temporary,path)
    @classmethod
    def load(cls,path):
        return cls(json.loads(Path(path).read_text(encoding='utf-8')))

def infer(ledger,now_ms,registry,rules,regime='UNKNOWN',previous=None):
    evidence=[normalize(r,now_ms,registry) for r in ledger.active(now_ms)]
    nodes={}; basis={}; conflict=[]
    # Facts from the same origin/metric/period/unit count once, including syndicated IDs.
    groups={}
    for r in evidence:
        if r['status']!='VERIFIED_CURRENT': continue
        key=(r['metric'],r['period'],r['unit'])
        groups.setdefault(key,[]).append(r)
    for key,rows in groups.items():
        signatures={tuple(r['numbers'].get(k) for k in ('actual','forecast','surprise')) for r in rows}
        if len(signatures)>1:
            conflict.append({'key':list(key),'evidence_ids':[r['id'] for r in rows]}); continue
        metric,period,unit=key
        # Do not mix periods/units into a single node implicitly.
        if metric in nodes: nodes[metric]='CONFLICT';continue
        surprise=rows[0]['numbers']['surprise']
        nodes[metric]='UNKNOWN' if surprise is None else 'UP' if Decimal(surprise)>0 else 'DOWN' if Decimal(surprise)<0 else 'FLAT'
        basis[metric]=[{'evidence_id':r['id'],'origin_id':r['origin_id'],'available_ms':r['available_ms']} for r in {r['origin_id']:r for r in rows}.values()]
    for item in conflict: nodes[item['key'][0]]='CONFLICT'
    trace=[]; pending=[]; rule_groups={}
    for rule in rules:
        if not all(rule.get(k) for k in ('id','target','horizon','rationale_fa','evidence_id','version','conditions','invalidates_fa','risks_fa')): raise ValueError('RULE_DOCUMENTATION')
        if rule['horizon'] not in ('short','medium','long') or rule.get('then') not in ('UP','DOWN','FLAT'): raise ValueError('RULE_SCHEMA')
        if type(rule.get('lag_ms')) is not int or rule['lag_ms']<0: raise ValueError('RULE_LAG')
        if rule['target'] in rule['conditions']: raise ValueError('SELF_CYCLE')
        rule_groups.setdefault(rule['target'],[]).append(rule)
    visited=set(nodes);ready_times={k:max(x['available_ms'] for x in v) for k,v in basis.items()}
    for target,alternatives in rule_groups.items():
        conclusions=set(); supports=[]; target_ready=[]
        for rule in alternatives:
            if any(n in rule_groups and n not in visited for n in rule['conditions']): raise ValueError('RULE_ORDER_OR_CYCLE')
            reasons=[]
            if rule.get('regime') not in ('ANY',regime): reasons.append('REGIME_UNKNOWN_OR_DIFFERENT')
            for node,expected in rule['conditions'].items():
                if expected not in ('UP','DOWN','FLAT'): raise ValueError('CONDITION_SCHEMA')
                if nodes.get(node)!=expected: reasons.append('CONDITION_'+node+'_'+nodes.get(node,'UNKNOWN'))
            roots=[x for node in rule['conditions'] for x in basis.get(node,[])]
            if not roots: reasons.append('NO_ROOT_EVIDENCE')
            ready=max((ready_times.get(n,now_ms) for n in rule['conditions']),default=now_ms)+rule['lag_ms']
            if now_ms<ready: reasons.append('LAG_NOT_REACHED')
            row={**copy.deepcopy(rule),'status':'CONDITIONAL_SUPPORTED' if not reasons else 'UNRESOLVED',
                 'reasons':reasons,'root_evidence':roots,'ready_ms':ready,'probability':None}
            if reasons: pending.append(row);continue
            conclusions.add(rule['then']); supports.extend(roots);target_ready.append(ready);trace.append(row)
        if conclusions:
            if target in nodes: conclusions.add(nodes[target])
            nodes[target]=next(iter(conclusions)) if len(conclusions)==1 else 'CONFLICT'
            basis[target]=list({(r['origin_id'],r['evidence_id']):r for r in supports}.values())
            ready_times[target]=max(target_ready)
        visited.add(target)
    changes=[]; old=(previous or {}).get('nodes',{})
    for node in sorted(set(old)|set(nodes)):
        if old.get(node)!=nodes.get(node): changes.append({'node':node,'before':old.get(node,'UNKNOWN'),'after':nodes.get(node,'UNKNOWN'),
            'reason_fa':'با بازخوانی شواهد فعال، اصلاح/حذف/کهنگی یا شرط رژیم و تأخیر، نتیجه دوباره محاسبه شد؛ امتیاز قبلی انباشته نشد.'})
    out={'model_version':MODEL_VERSION,'asof_ms':now_ms,'regime':regime,'evidence':evidence,'nodes':nodes,
         'scenarios':trace+pending,'contradictions':conflict,'changes':changes,'probability':None,
         'forecast_validated':False,'can_authorize_orders':False,'ledger_head':ledger.entries[-1]['hash'] if ledger.entries else None}
    out['analysis_id']=digest(out);return out

def render_fa(report):
    lines=['تقویم اقتصادی امین — تحلیل شرطی، بدون مجوز معامله','وضعیت فعلی:']
    for r in report['evidence']:
        n=r['numbers'];lines.append(f"{r['metric']} | {r['status']} | دوره {r['period']} | واحد {r['unit']} | قبلی {n['previous']} | پیش‌بینی {n['forecast']} | واقعی {n['actual']} | تغییر {n['change']} | غافلگیری {n['surprise']}\nمنبع: {r['source_url']}\nانتشار: {r.get('published_at')}؛ بررسی: {r.get('checked_at')}؛ دلایل: {', '.join(r['reasons'])}")
    lines.append('تغییرات جدید:')
    for c in report['changes']:lines.append(f"{c['node']}: {c['before']} → {c['after']}؛ {c['reason_fa']}")
    lines.append('تحلیل اقتصادی و آینده‌پژوهی:')
    for s in report['scenarios']:lines.append(f"{s['horizon']} | {s['target']} | {s['status']} | فرض: {s['conditions']} | {s['rationale_fa']} | شواهد: {[r['evidence_id'] for r in s['root_evidence']]} | نقض: {s['invalidates_fa']} | خطر: {s['risks_fa']} | دلایل عدم احراز: {s['reasons']}")
    lines.append('ارزیابی عملکرد: احتمال عددی و دقت معتبر هنوز موجود نیست. این روابط فرضیه‌اند، نه علیت یا پیش‌بینی قطعی.')
    lines.append('شناسه تحلیل: '+report['analysis_id']);return '\n'.join(lines)
