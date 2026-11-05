"""Typed calendar evidence is a veto/confirmation layer, never an order generator.

Narrative and model supplied approval/accuracy claims are deliberately ignored.
The same pure policy is used for prospective evaluation and runtime decisions.
"""
import hashlib
import json
from datetime import date, datetime, timezone
from pathlib import Path
from .sources import SOURCES

HORIZON_MS = 2 * 60 * 60 * 1000
MAX_SOURCE_AGE_MS = 180000
SHORT_SOURCES = {'fed-news', 'bls-news', 'us-10y', 'oil-wti', 'natural-events', 'world-risk-news'}


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False, allow_nan=False).encode()).hexdigest()


def evidence_fingerprint(evidence,source_ids=None):
    """Rechecking the same fact at a new clock cannot create independent evidence."""
    sources=[]
    for row in evidence.get('public_sources',[]):
        if not isinstance(row,dict) or row.get('status')!='available' or (source_ids is not None and row.get('id') not in source_ids):continue
        normalized={k:row[k] for k in ('id','source_url','latest','previous','frequency') if k in row}
        if isinstance(row.get('records'),list):
            records={digest(r):r for r in row['records'] if isinstance(r,dict)}
            normalized['records']=[records[key] for key in sorted(records)]
        sources.append(normalized)
    return digest(sorted(sources,key=lambda x:x.get('id','')))


def policy_version(baseline_sha256=None):
    names = ('calendar_policy.py', 'support.py', 'research_context.py', 'forecast_evaluation.py',
             'foresight_catalog.py','foresight_method.py','cross_impact.py','scenario_grid.py','local_research.py','sources.py','runtime.py','strategy.py','analysis.py')
    code=hashlib.sha256(b''.join(n.encode()+b'\0'+Path(__file__).with_name(n).read_bytes() for n in names)).hexdigest()
    if baseline_sha256 is None:return code
    if not isinstance(baseline_sha256,str) or len(baseline_sha256)!=64 or any(c not in '0123456789abcdef' for c in baseline_sha256):
        raise ValueError('Exact baseline artifact digest required')
    return digest({'calendar_code':code,'baseline_strategy_sha256':baseline_sha256})


def parse_response(text):
    """A legacy narrative remains readable, but cannot become a trading signal."""
    try:
        value = json.loads(text)
        if not isinstance(value, dict) or set(value) != {'summary', 'short_term', 'long_term'}:
            raise ValueError('Unexpected research schema')
        if not isinstance(value['summary'], str) or not 1 <= len(value['summary']) <= 5000:
            raise ValueError('Invalid summary')
        for horizon in ('short_term', 'long_term'):
            scenario = value[horizon]
            if not isinstance(scenario, dict) or set(scenario) != {'direction', 'uncertainty', 'source_ids'}:
                raise ValueError('Invalid scenario')
            if scenario['direction'] not in ('buy', 'sell', 'neutral') or scenario['uncertainty'] not in ('low', 'medium', 'high'):
                raise ValueError('Invalid direction or uncertainty')
            ids = scenario['source_ids']
            if not isinstance(ids, list) or not 0 <= len(ids) <= 6 or any(not isinstance(x, str) for x in ids) or len(set(ids)) != len(ids):
                raise ValueError('Invalid source references')
            if not set(ids) <= {s.id for s in SOURCES}:
                raise ValueError('Unknown source')
        return value['summary'], {'schema': 1, 'symbol': 'XAUUSD', 'horizon_ms': HORIZON_MS,
                                  'short_term': value['short_term'], 'long_term': value['long_term']}
    except (ValueError, TypeError, KeyError):
        return text, None


def _usable(row, now):
    if row.get('status') != 'available' or type(row.get('checked_ms')) is not int or not 0 <= now-row['checked_ms'] <= MAX_SOURCE_AGE_MS:
        return False
    latest = row.get('latest')
    if isinstance(latest, dict):
        try:
            day = date.fromisoformat(latest['observation_date'])
            today = datetime.fromtimestamp(now/1000, timezone.utc).date()
            if type(latest.get('value')) not in (int, float) or not __import__('math').isfinite(latest['value']):return False
            return 0 <= (today-day).days <= 7
        except (ValueError, TypeError, KeyError):return False
    records=row.get('records', [])
    if not isinstance(records,list):return False
    return any(isinstance(r, dict) and type(r.get('published_ms')) is int and
               0 <= now-r['published_ms'] <= 7*86400000 and isinstance(r.get('title'), str) and bool(r['title'].strip())
               for r in records)


def assess(report, now_ms, side, symbol='XAUUSD'):
    """Assess the evidence only; success is NOT permission to trade."""
    result = {'allowed': False, 'reason': 'CALENDAR_REPORT_MISSING', 'candidate_side': side,
              'observed_ms': now_ms, 'policy_sha256': policy_version(), 'report_id': None,
              'effect': 'blocked', 'source_ids': [], 'horizon_ms': HORIZON_MS}
    if not isinstance(report, dict):return result
    result['report_id'] = digest(report)
    result['generated_ms'] = report.get('generated_ms')
    def reject(reason):
        result['reason'] = reason
        return result
    if report.get('scope', 'global') != 'global':return reject('CALENDAR_SCOPE_MISMATCH')
    generated = report.get('generated_ms')
    if type(generated) is not int or not 0 <= now_ms-generated <= MAX_SOURCE_AGE_MS:return reject('CALENDAR_REPORT_STALE')
    signal = report.get('decision_signal')
    if not isinstance(signal, dict):return reject('CALENDAR_SIGNAL_MISSING')
    # Re-parse the bounded schema rather than accepting arbitrary persisted fields.
    _, checked = parse_response(json.dumps({'summary': 'schema-check', 'short_term': signal.get('short_term'), 'long_term': signal.get('long_term')}))
    if checked is None or signal != checked:return reject('CALENDAR_SIGNAL_INVALID')
    canonical_symbol='XAUUSD' if symbol in ('XAUUSD','XAUUSD.st','XAUUSD.fix','XAUUSD.zero') else symbol
    if canonical_symbol != signal['symbol']:return reject('CALENDAR_SYMBOL_MISMATCH')
    evidence = report.get('evidence')
    if not isinstance(evidence, dict) or type(evidence.get('generated_ms')) is not int or not 0 <= generated-evidence['generated_ms'] <= MAX_SOURCE_AGE_MS:
        return reject('CALENDAR_EVIDENCE_MISSING')
    known = {s.id: s.url for s in SOURCES}
    rows = evidence.get('public_sources', [])
    if not isinstance(rows, list):return reject('CALENDAR_EVIDENCE_MISSING')
    usable = {r['id'] for r in rows if isinstance(r, dict) and r.get('id') in SHORT_SOURCES and
              r.get('source_url') == known.get(r.get('id')) and type(r.get('checked_ms')) is int and
              r['checked_ms'] <= evidence['generated_ms'] and _usable(r, now_ms)}
    short, long = signal['short_term'], signal['long_term']
    result.update(direction=short['direction'], uncertainty=short['uncertainty'], source_ids=short['source_ids'])
    if len(short['source_ids']) < 2 or not set(short['source_ids']) <= usable:return reject('CALENDAR_SOURCES_INSUFFICIENT')
    if short['uncertainty'] != 'low':return reject('CALENDAR_UNCERTAINTY_HIGH')
    if short['direction'] == 'neutral':return reject('CALENDAR_DIRECTION_UNKNOWN')
    if long['direction'] in ('buy', 'sell') and long['uncertainty'] != 'high':
        if len(long['source_ids']) < 2 or not set(long['source_ids']) <= usable:return reject('CALENDAR_SOURCES_INSUFFICIENT')
        if long['direction'] != short['direction']:return reject('CALENDAR_HORIZON_CONFLICT')
    if side not in ('buy', 'sell'):return reject('CALENDAR_NO_PRICE_CANDIDATE')
    if short['direction'] != side:return reject('CALENDAR_OPPOSES_CANDIDATE')
    result.update(allowed=True, reason='CALENDAR_CONFIRMS_CANDIDATE', effect='confirmed')
    return result


def entry_decision(policy,news,report,evaluation,now_ms,side,symbol='XAUUSD',baseline_sha256=None):
    if policy.entry_context_mode!='scheduled-news-v1':
        return decision(report,evaluation,now_ms,side,symbol,baseline_sha256)
    # Only a freshly inspected trusted NewsGate supplies this context. Price
    # strategy validation and all execution risk checks remain independent.
    valid=(isinstance(news,dict) and news.get('clear') is True and news.get('reason')=='covered'
           and type(news.get('received_ms')) is int and 0<=now_ms-news['received_ms']<=120000
           and news.get('source')=='MT5-MetaQuotes-calendar'
           and symbol in ('XAUUSD','XAUUSD.st','XAUUSD.fix','XAUUSD.zero'))
    evidence={k:news.get(k) for k in ('source','received_ms','coverage_start_ms','coverage_end_ms','events')} if isinstance(news,dict) else {}
    candidate=side in ('buy','sell')
    return {'allowed':valid and candidate,'reason':('CALENDAR_NO_PRICE_CANDIDATE' if valid and not candidate else 'SCHEDULED_NEWS_CLEAR' if valid else 'SCHEDULED_NEWS_BLOCKED'),
            'effect':'context_only' if valid else 'blocked','report_id':digest(evidence),
            'mode':'scheduled-news-v1','directional_prediction':False}


def decision(report, evaluation, now_ms, side, symbol='XAUUSD',baseline_sha256=None):
    result = assess(report, now_ms, side, symbol)
    result['policy_sha256']=policy_version(baseline_sha256)
    result['evidence_allowed'] = result['allowed']
    if not result['allowed']:return result
    valid = (isinstance(evaluation, dict) and evaluation.get('deployment_eligible') is True and
             evaluation.get('policy_sha256') == result['policy_sha256'] and
             type(evaluation.get('issued_ms')) is int and type(evaluation.get('expires_ms')) is int and
             evaluation.get('horizon_ms') == HORIZON_MS and
             set(result['source_ids']) <= set(evaluation.get('source_ids',[])) and
             sorted(result['source_ids']) == evaluation.get('evaluation_scope_source_ids') and
             0 <= now_ms-evaluation['issued_ms'] <= 7*86400000 and now_ms < evaluation['expires_ms'] <= evaluation['issued_ms']+7*86400000)
    if not valid:result.update(allowed=False, reason='CALENDAR_VALIDATION_REQUIRED', effect='blocked')
    result['evaluation_id'] = digest(evaluation) if isinstance(evaluation, dict) else None
    return result


REASONS_FA = {
 'SCHEDULED_NEWS_CLEAR': 'پوشش تازهٔ تقویم تأیید شد؛ در پنجرهٔ خبر مهم نیستیم. این تأیید جهت معامله نیست.',
 'SCHEDULED_NEWS_BLOCKED': 'پوشش تازهٔ تقویم تأیید نشده یا در پنجرهٔ خبر مهم هستیم؛ ورود منتظر می‌ماند.',
 'CALENDAR_REPORT_MISSING': 'گزارش پژوهش تقویم هنوز ثبت نشده است.',
 'CALENDAR_REPORT_STALE': 'گزارش پژوهش تازه نیست یا زمان معتبر ندارد.',
 'CALENDAR_SIGNAL_MISSING': 'گزارش فقط متن دارد؛ نتیجهٔ ساختاریافته برای تصمیم ندارد.',
 'CALENDAR_SIGNAL_INVALID': 'ساختار نتیجهٔ پژوهش معتبر نیست.',
 'CALENDAR_SCOPE_MISMATCH': 'گزارش آماری ایران در تصمیم معامله مصرف نمی‌شود.',
 'CALENDAR_SYMBOL_MISMATCH': 'موضوع پژوهش با نماد معامله یکسان نیست.',
 'CALENDAR_EVIDENCE_MISSING': 'شاهد زمان‌دار پژوهش کافی نیست.',
 'CALENDAR_SOURCES_INSUFFICIENT': 'حداقل دو منبع تازه و قابل ارجاع لازم است.',
 'CALENDAR_UNCERTAINTY_HIGH': 'عدم قطعیت پژوهش برای استفاده در معامله کافی کاهش نیافته است؛ ورود رد شد.',
 'CALENDAR_DIRECTION_UNKNOWN': 'پژوهش جهت روشنی برای طلا ندارد.',
 'CALENDAR_HORIZON_CONFLICT': 'سناریوهای کوتاه‌مدت و بلندمدت تعارض دارند.',
 'CALENDAR_NO_PRICE_CANDIDATE': 'نامزد معتبر قیمت برای تأیید پژوهش وجود ندارد.',
 'CALENDAR_OPPOSES_CANDIDATE': 'جهت پژوهش با نامزد معامله مخالف است؛ ورود رد شد.',
 'CALENDAR_VALIDATION_REQUIRED': 'اثر پژوهش هنوز ارزیابی مستقل کافی ندارد؛ سفارش مجاز نیست.',
 'CALENDAR_CONFIRMS_CANDIDATE': 'پژوهش نامزد معامله را تأیید کرد؛ محافظ ریسک مستقل تصمیم نهایی را می‌گیرد.'}


def public_decision(value):
    if not isinstance(value, dict):return {'reason_fa': 'هنوز تصمیم تازه‌ای از موتور دریافت نشده است.'}
    return {**value, 'reason_fa': REASONS_FA.get(value.get('reason'), 'وضعیت پژوهش نیازمند بررسی است.')}
