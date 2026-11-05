"""Bounded official-source ingestion. Supplemental feeds never clear the news gate."""
from dataclasses import dataclass,asdict
from datetime import datetime,timezone
from email.utils import parsedate_to_datetime
import argparse
import csv
import hashlib
import html
import io
import json
import math
from pathlib import Path
import re
import time
import urllib.request
import urllib.error
from urllib.parse import urlsplit,quote
import xml.etree.ElementTree as ET
from zoneinfo import ZoneInfo


@dataclass(frozen=True)
class Source:
    id:str
    url:str
    kind:str
    policy_url:str
    ttl_seconds:int=3600
    max_bytes:int=2000000
    usage:str='Attributed supplemental public data; no complete-calendar or live-execution entitlement claimed'


SOURCES=(
    Source('fed-news','https://www.federalreserve.gov/feeds/press_all.xml','rss','https://www.federalreserve.gov/aboutthefed/website-linking-policies.htm'),
    Source('bls-news','https://www.bls.gov/feed/bls_latest.rss','rss','https://www.bls.gov/bls/linksite.htm'),
    Source('bls-calendar','https://www.bls.gov/schedule/news_release/bls.ics','ics','https://www.bls.gov/bls/linksite.htm'),
    Source('us-10y','https://fred.stlouisfed.org/graph/fredgraph.csv?id=DGS10','csv','https://fred.stlouisfed.org/legal/',86400),
    Source('research-discovery','https://export.arxiv.org/api/query?search_query=cat:q-fin.TR&start=0&max_results=5&sortBy=submittedDate&sortOrder=descending','atom','https://info.arxiv.org/help/api/tou.html',86400),
    Source('research-crossref','https://api.crossref.org/works?query.bibliographic=gold%20price%20forecasting&filter=type:journal-article&rows=5&select=DOI,title,published','crossref','https://www.crossref.org/documentation/retrieve-metadata/rest-api/',86400),
    Source('oil-wti','https://fred.stlouisfed.org/graph/fredgraph.csv?id=DCOILWTICO','oil-csv','https://fred.stlouisfed.org/legal/',86400),
    Source('world-growth','https://api.worldbank.org/v2/country/all/indicator/NY.GDP.MKTP.KD.ZG?format=json&mrnev=1&per_page=400','worldbank','https://datahelpdesk.worldbank.org/knowledgebase/articles/889392',86400),
    Source('natural-events','https://www.gdacs.org/xml/rss.xml','rss','https://www.gdacs.org/documents/gdacs%20guidelines%202014_-_final.pdf'),
    Source('world-risk-news','https://api.gdeltproject.org/api/v2/doc/doc?query=%28gold%20OR%20oil%29%20%28war%20OR%20economy%29&mode=ArtList&maxrecords=20&format=json&timespan=1d','gdelt','https://blog.gdeltproject.org/gdelt-doc-2-0-api-debuts/'),
    Source('copytrade-discovery','https://www.mql5.com/en/signals','copy-directory','https://www.mql5.com/en/signals/rules',3600),
    Source('foresight-cimorg','https://cimorg.org/feed/','foresight-rss','https://cimorg.org/',3600),

)


def plain(value,limit=1500):return html.unescape(re.sub('<[^>]*>',' ',value or '')).strip()[:limit]


def safe_xml(raw):
    upper=raw.upper()
    if b'<!DOCTYPE' in upper or b'<!ENTITY' in upper:raise ValueError('XML entities are not allowed')
    return ET.fromstring(raw)


def publication(value):
    if not value:return None
    try:
        dt=datetime.fromisoformat(value.replace('Z','+00:00'))
    except ValueError:dt=parsedate_to_datetime(value)
    if dt.tzinfo is None:raise ValueError('Publication time lacks zone')
    return int(dt.timestamp()*1000)


def parse_rss(raw,source,received):
    root=safe_xml(raw);records=[]
    for item in root.findall('./channel/item')[:100]:
        title=plain(item.findtext('title'),300);published=publication(item.findtext('pubDate'))
        if published is not None and published>received+300000:continue
        link=(item.findtext('link') or '').strip()
        if urlsplit(link).hostname!=urlsplit(source.url).hostname:continue
        records.append({'id':hashlib.sha256((source.id+link+title).encode()).hexdigest(),'title':title,'url':link,
                        'summary':plain(item.findtext('description')),'published_ms':published,'received_ms':received,
                        'available_ms':max(received,published or received),'source':source.id,'timing_verified':published is not None})
    if not records:raise ValueError('No usable feed records')
    return {'records':records,'coverage_complete':False,'may_clear_news_gate':False}


def parse_ics(raw,source,received):
    text=raw.decode('utf-8-sig');text=re.sub(r'\r?\n[ \t]','',text)
    events=[];current=None
    for line in text.splitlines():
        line=line.strip()
        if line=='BEGIN:VEVENT':current={}
        elif line=='END:VEVENT' and current is not None:
            title=plain(current.get('SUMMARY',''),300)
            when=current.get('start')
            if title and when:
                events.append({'id':current.get('UID',hashlib.sha256((title+str(when)).encode()).hexdigest()),'title':title,
                               'time_ms':when,'currency':'USD','impact':'high' if any(k in title.lower() for k in ('consumer price','producer price','employment situation','employment cost')) else 'medium',
                               'source':source.id,'received_ms':received,'available_ms':received})
            current=None
        elif current is not None and ':' in line:
            key,value=line.split(':',1)
            if key.startswith('DTSTART'):
                if value.endswith('Z'):dt=datetime.strptime(value,'%Y%m%dT%H%M%SZ').replace(tzinfo=timezone.utc)
                elif 'TZID=' in key:
                    zone=key.split('TZID=',1)[1].strip('"')
                    zone={'US-Eastern':'America/New_York','US/Eastern':'America/New_York'}.get(zone,zone)
                    if zone not in ('America/New_York','UTC'):raise ValueError('Unreviewed calendar time zone')
                    dt=datetime.strptime(value,'%Y%m%dT%H%M%S').replace(tzinfo=ZoneInfo(zone))
                    if dt.replace(fold=0).utcoffset()!=dt.replace(fold=1).utcoffset():raise ValueError('Ambiguous event time')
                else:raise ValueError('Calendar start lacks an explicit time zone')
                current['start']=int(dt.timestamp()*1000)
            else:current[key.split(';')[0]]=value.replace('\\,',',').replace('\\n',' ')
    if not events:raise ValueError('No calendar events')
    unique={event['id']:event for event in events}
    return {'events':sorted(unique.values(),key=lambda e:e['time_ms']),'coverage_complete':False,'may_clear_news_gate':False,
            'scope':'BLS releases only; FOMC, private releases and unscheduled events not covered'}


def parse_yield(raw,source,received):
    rows=list(csv.DictReader(io.StringIO(raw.decode('utf-8-sig'))))
    records=[];previous='';today=datetime.fromtimestamp(received/1000,timezone.utc).date()
    for r in rows:
        date=r['observation_date']
        if date<=previous or datetime.fromisoformat(date).date()>today:raise ValueError('Invalid macro observation dates')
        previous=date
        if r['DGS10'] in ('','.'):continue
        value=float(r['DGS10'])
        if not math.isfinite(value) or not -10<=value<=50:raise ValueError('Invalid yield value')
        records.append({'observation_date':date,'value':value,'unit':'percent','available_ms':received})
    if not records:raise ValueError('No macro data')
    return {'series':'DGS10','title':'US Treasury 10-year constant maturity yield','frequency':'daily','latest':records[-1],'previous':records[-2] if len(records)>1 else None,
            'history_rows':len(records),'received_ms':received,'historical_publication_times_verified':False,
            'usage':'advisory only; observation date is not an intraday availability timestamp','may_clear_news_gate':False}


def parse_discovery(raw,source,received):
    root=safe_xml(raw);ns={'a':'http://www.w3.org/2005/Atom'};records=[]
    for entry in root.findall('a:entry',ns)[:20]:
        title=plain(entry.findtext('a:title',default='',namespaces=ns),300)
        abstract=plain(entry.findtext('a:summary',default='',namespaces=ns),2500)
        published=publication(entry.findtext('a:published',default='',namespaces=ns))
        url=entry.findtext('a:id',default='',namespaces=ns).replace('http://arxiv.org/','https://arxiv.org/')
        if not title or urlsplit(url).hostname!='arxiv.org' or (published and published>received+300000):continue
        families=[n for n,terms in {'trend':['momentum','trend'],'reversion':['mean reversion','reversal'],'liquidity':['liquidity','order flow'],'regime':['regime','volatility']}.items() if any(t in (title+' '+abstract).lower() for t in terms)]
        records.append({'id':hashlib.sha256(url.encode()).hexdigest(),'title':title,'abstract':abstract,'url':url,
                        'families':families,'published_ms':published,'received_ms':received,'available_ms':received,'source':source.id,
                        'status':'quarantined_proposal','code_downloaded':False,'execution_enabled':False,'license_review_required_before_full_text_use':True})
    return {'records':records,'promotion_allowed':False,'metadata_only':True}


def parse_crossref(raw,source,received):
    data=json.loads(raw)
    if not isinstance(data,dict) or not isinstance(data.get('message'),dict):raise ValueError('Invalid metadata response')
    items=data['message'].get('items')
    if not isinstance(items,list):raise ValueError('Invalid metadata response')
    records=[]
    for item in items[:20]:
        if not isinstance(item,dict):continue
        doi=item.get('DOI','');titles=item.get('title',[])
        if not isinstance(doi,str) or len(doi)>250 or not re.fullmatch(r'10\.[0-9]{4,9}/[^\s<>"#?]+',doi) or not isinstance(titles,list) or not titles or not isinstance(titles[0],str):continue
        title=plain(titles[0],300)
        # Keyword match is relevance screening, never proof of scientific quality.
        if not title or not re.search(r'gold|precious metal',title,re.I):continue
        published=None
        try:
            parts=item['published']['date-parts'][0]
            published=int(datetime(int(parts[0]),int(parts[1]) if len(parts)>1 else 1,int(parts[2]) if len(parts)>2 else 1,tzinfo=timezone.utc).timestamp()*1000)
        except (KeyError,TypeError,ValueError,IndexError,OverflowError):pass
        if published is not None and published>received+300000:continue
        url='https://doi.org/'+quote(doi,safe='/().;:-_')
        records.append({'id':hashlib.sha256(url.lower().encode()).hexdigest(),'title':title,'url':url,'families':[],
                        'published_ms':published,'received_ms':received,'available_ms':received,'source':source.id,
                        'status':'quarantined_proposal','code_downloaded':False,'execution_enabled':False,
                        'license_review_required_before_full_text_use':True,'scientific_quality_verified':False})
    return {'records':records,'promotion_allowed':False,'metadata_only':True}


def parse_oil(raw,source,received):
    rows=list(csv.DictReader(io.StringIO(raw.decode('utf-8-sig'))));records=[];previous=''
    today=datetime.fromtimestamp(received/1000,timezone.utc).date()
    for row in rows:
        date=row['observation_date']
        if date<=previous or datetime.fromisoformat(date).date()>today:raise ValueError('Invalid oil observation dates')
        previous=date
        if row['DCOILWTICO'] in ('','.'):continue
        value=float(row['DCOILWTICO'])
        if not math.isfinite(value) or not -200<=value<=1000:raise ValueError('Invalid oil observation')
        records.append({'observation_date':date,'value':value,'unit':'USD/barrel','available_ms':received})
    if not records:raise ValueError('No oil data')
    return {'series':'DCOILWTICO','frequency':'daily','latest':records[-1],'previous':records[-2] if len(records)>1 else None,'history_rows':len(records),
            'historical_publication_times_verified':False,'may_clear_news_gate':False,'price_effect_verified':False}


def parse_worldbank(raw,source,received):
    data=json.loads(raw)
    if not isinstance(data,list) or len(data)!=2 or not isinstance(data[0],dict) or not isinstance(data[1],list):raise ValueError('Invalid economic data')
    records=[];year=datetime.fromtimestamp(received/1000,timezone.utc).year
    for row in data[1][:400]:
        try:
            code=row['countryiso3code'];value=float(row['value']);period=int(row['date']);name=plain(row['country']['value'],120)
            if not re.fullmatch('[A-Z]{3}',code) or not 1900<=period<=year or not math.isfinite(value):continue
        except (KeyError,TypeError,ValueError):continue
        records.append({'id':hashlib.sha256((code+str(period)).encode()).hexdigest(),'title':name+' — GDP growth '+str(period),
                        'geography_code':code,'geography':name,'period':period,'value':value,'unit':'percent/year',
                        'url':source.url,'available_ms':received,'includes_geographic_aggregates':True})
    if not records:raise ValueError('No economic observations')
    return {'records':records,'frequency':'annual','all_pages_received':data[0].get('pages')==1,
            'historical_publication_times_verified':False,'price_effect_verified':False,'may_clear_news_gate':False}


def parse_gdelt(raw,source,received):
    data=json.loads(raw)
    if not isinstance(data,dict) or not isinstance(data.get('articles'),list):raise ValueError('Invalid news metadata')
    records=[]
    for row in data['articles'][:20]:
        url=row.get('url','');title=plain(row.get('title',''),300)
        try:
            parsed=urlsplit(url)
            if parsed.scheme!='https' or not parsed.hostname or parsed.username or parsed.password or parsed.port not in (None,443):continue
            seen=int(datetime.strptime(row['seendate'],'%Y%m%dT%H%M%SZ').replace(tzinfo=timezone.utc).timestamp()*1000)
            if seen>received+300000:continue
        except (ValueError,TypeError,KeyError):continue
        if not title:continue
        records.append({'id':hashlib.sha256(url.encode()).hexdigest(),'title':title,'url':url,
                        'source_country':plain(row.get('sourcecountry',''),80),'seen_by_provider_ms':seen,
                        'received_ms':received,'available_ms':received,'facts_verified':False,'price_effect_verified':False})
    return {'records':records,'scope':'keyword-selected international news metadata; not full world coverage',
            'may_clear_news_gate':False,'facts_verified':False}


def parse_copy_directory(raw,source,received):
    text=raw.decode('utf-8','replace');records=[]
    # Only public numeric profile links; no account/login/subscription endpoint is visited.
    for identity in dict.fromkeys(re.findall(r'href=["\'](/en/signals/[0-9]{1,9})["\']',text)):
        url='https://www.mql5.com'+identity
        records.append({'id':hashlib.sha256(url.encode()).hexdigest(),'title':'Public signal profile '+identity.rsplit('/',1)[-1],
                        'url':url,'source':source.id,'received_ms':received,'available_ms':received,'status':'quarantined_proposal',
                        'win_rate_percent':None,'meets_requested_win_rate':None,'statistics_verified':False,
                        'execution_enabled':False,'code_downloaded':False,'license_review_required_before_full_text_use':True})
        if len(records)>=5:break
    if not records:raise ValueError('No public signal profiles')
    return {'records':records,'metadata_only':True,'promotion_allowed':False,'requested_win_rate_percent':80,
            'scope':'public profile discovery only; win rate, drawdown and track record still require review'}


def cache_valid(previous,source,now,poll_seconds=None):
    if not isinstance(previous,dict):return False
    received=previous.get('checked_ms',previous.get('received_ms'))
    if type(received) is not int or now<received:return False
    if previous.get('status')=='usable_supplemental':return now-received<(min(source.ttl_seconds,poll_seconds) if poll_seconds is not None else source.ttl_seconds)*1000
    failures=previous.get('consecutive_failures',1)
    failures=failures if type(failures) is int else 1
    delay=min(3600,300*2**max(0,min(failures-1,4)))
    return now-received<delay*1000


def parse_foresight(raw,source,received):
    result=parse_rss(raw,source,received)
    for row in result['records']:
        row.pop('summary',None)
        row.update(status='quarantined_method_context',execution_enabled=False,code_downloaded=False,
                   license_review_required_before_full_text_use=True,accuracy_verified=False)
    return {**result,'metadata_only':True,'promotion_allowed':False}


def parse(raw,source,received):
    if len(raw)>source.max_bytes:raise ValueError('Source response too large')
    return {'rss':parse_rss,'ics':parse_ics,'csv':parse_yield,'atom':parse_discovery,'crossref':parse_crossref,'oil-csv':parse_oil,'worldbank':parse_worldbank,'gdelt':parse_gdelt,'copy-directory':parse_copy_directory,'foresight-rss':parse_foresight}[source.kind](raw,source,received)


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self,*args,**kwargs):raise ValueError('Unreviewed source redirect')


def _collect_source(root,source,now_ms):
    metadata=root/(source.id+'.latest.json')
    try:previous=json.loads(metadata.read_text()) if metadata.exists() else None
    except (ValueError,OSError):previous=None
    if cache_valid(previous,source,now_ms,60):
        return previous
    started=time.monotonic()
    try:
        headers={'User-Agent':'AminResearch/0.4 bounded feed client'}
        if previous and previous.get('status')=='usable_supplemental':
            for key,header in [('etag','If-None-Match'),('last_modified','If-Modified-Since')]:
                value=previous.get(key)
                if isinstance(value,str) and len(value)<=512 and '\n' not in value and '\r' not in value:headers[header]=value
        request=urllib.request.Request(source.url,headers=headers)
        if source.id in ('us-10y','oil-wti','world-growth','research-discovery'):
            from .public_http import public_get
            public=public_get(source.url,max_bytes=source.max_bytes,timeout=10)
            raw=public.content;etag=modified=None
        else:
            with urllib.request.build_opener(NoRedirect()).open(request,timeout=10) as response:
                if response.status!=200:raise ValueError('HTTP source error')
                etag=response.headers.get('ETag');modified=response.headers.get('Last-Modified')
                raw=response.read(source.max_bytes+1)
                if len(raw)>source.max_bytes:raise ValueError('Source too large')
        received=int(time.time()*1000);data=parse(raw,source,received)
        digest=hashlib.sha256(raw).hexdigest()
        archive=root/f'{source.id}-{digest}.raw'
        if not archive.exists():
            with archive.open('xb') as f:f.write(raw)
        observation={'id':source.id,'url':source.url,'policy_url':source.policy_url,'received_ms':received,
                     'sha256':digest,'checked_ms':received,'etag':etag,'last_modified':modified,'elapsed_ms':int((time.monotonic()-started)*1000),
                     'status':'usable_supplemental','consecutive_failures':0,'last_success_ms':received,'usage':source.usage,'live_calendar_approved':False,'data':data}
    except Exception as e:
        if isinstance(e,urllib.error.HTTPError) and e.code==304 and isinstance(previous,dict) and previous.get('status')=='usable_supplemental':
            observation=dict(previous,checked_ms=int(time.time()*1000),not_modified=True)
            metadata.write_text(json.dumps(observation,allow_nan=False,indent=2));return observation
        old=previous if isinstance(previous,dict) else {}
        count=old.get('consecutive_failures',0)
        count=min(10,max(0,count))+1 if type(count) is int else 1
        observation={'id':source.id,'url':source.url,'status':'unavailable','received_ms':now_ms,'error':type(e).__name__,
                     'may_clear_news_gate':False,'consecutive_failures':count,'retry_after_seconds':min(3600,300*2**min(count-1,4)),
                     'http_status':e.code if isinstance(e,urllib.error.HTTPError) else None,'last_success_ms':old.get('last_success_ms')}
    # Latest pointers are replaceable; immutable raw snapshots remain preserved.
    metadata.write_text(json.dumps(observation,allow_nan=False,indent=2));return observation


def collect(directory,now_ms=None):
    from concurrent.futures import ThreadPoolExecutor
    root=Path(directory);root.mkdir(parents=True,exist_ok=True)
    now_ms=int(time.time()*1000) if now_ms is None else now_ms
    from .source_priority import prioritized,role
    previous={}
    for source in SOURCES:
        try:previous[source.id]=json.loads((root/(source.id+'.latest.json')).read_text())
        except (OSError,ValueError):pass
    ordered=prioritized(SOURCES,previous,now_ms)
    # Primary public data first, latency only within each reviewed role.
    # Independent fixed hosts, bounded to three concurrent requests; no overlapping batch.
    with ThreadPoolExecutor(max_workers=3) as pool:
        observations=list(pool.map(lambda source:_collect_source(root,source,now_ms),ordered))
    observations=[dict(row,collection_priority=i+1,source_role=role(row['id'])) for i,row in enumerate(observations)]
    return {'observed_ms':now_ms,'source_priority_policy':'reviewed-primary-then-context-v1','sources':observations,'complete_calendar':False,'may_clear_news_gate':False,
            'iran_access_verified':False,'broker_latency_verified':False}


def main():
    p=argparse.ArgumentParser();p.add_argument('directory');p.add_argument('output');a=p.parse_args()
    result=collect(a.directory)
    with Path(a.output).open('x') as f:json.dump(result,f,allow_nan=False,indent=2)


if __name__=='__main__':main()
