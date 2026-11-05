"""Actual local factual synthesis: public inputs only, no model/network/cost.

Evidence comparison and a source-traceable scenario workflow are executable.
They do not manufacture a gold price direction from macro correlation stories.
"""
from datetime import date,datetime,timezone
import math
from .research_context import public_context
from .calendar_policy import evidence_fingerprint,policy_version,HORIZON_MS


def _valid_number(value):
    return type(value) in (int,float) and math.isfinite(value)


def _month_ordinal(period):
    year,month=map(int,period.split('-'))
    if not 1<=month<=12:raise ValueError('Invalid statistical month')
    return year*12+month


def _drivers(evidence,now):
    drivers=[]
    for row in evidence['public_sources']:
        if row['status']!='available':continue
        latest,prior=row.get('latest'),row.get('previous')
        if not isinstance(latest,dict) or not _valid_number(latest.get('value')):continue
        try:
            current_day=date.fromisoformat(latest['observation_date'])
            if not 0<=(datetime.fromtimestamp(now/1000,timezone.utc).date()-current_day).days<=7:continue
        except (ValueError,TypeError,KeyError):continue
        comparable=False
        if isinstance(prior,dict) and _valid_number(prior.get('value')):
            try:comparable=prior['unit']==latest['unit'] and 0<(current_day-date.fromisoformat(prior['observation_date'])).days<=7
            except (ValueError,TypeError,KeyError):pass
        drivers.append({'id':row['id'],'source_id':row['id'],'actor':'public-market-observation',
                        'title':row['id'],'value':latest['value'],'previous_value':prior['value'] if comparable else None,
                        'observed_ms':row['checked_ms'],'published_ms':None,'period':latest['observation_date'],
                        'previous_period':prior['observation_date'] if comparable else None,
                        'unit':latest['unit'],'source_url':row['source_url'],
                        'frequency':'daily','previous_unit':prior['unit'] if comparable else latest['unit'],
                        'change':latest['value']-prior['value'] if comparable else None})
    return drivers


def calendar_report(feeds,now_ms,previous_framework=None):
    from .foresight_method import analyze
    evidence=public_context(feeds,now_ms)
    drivers=_drivers(evidence,now_ms)
    evidence['driver_observations']=drivers
    framework=analyze(evidence,now_ms,previous=previous_framework)
    lines=['گزارش محلی بر پایهٔ دادهٔ عمومی واقعی؛ هیچ داده‌ای برای این گزارش به مدل بیرونی ارسال نشده است.',
           'وضعیت داده و گذشته:']
    for row in drivers:
        name={'us-10y':'بازده اوراق ده‌سالهٔ آمریکا','oil-wti':'قیمت روزانه نفت WTI'}.get(row['id'],row['title'])
        text=f"{name}: {row['value']:g} {row['unit']}؛ دورهٔ مشاهده {row['period']}"
        if row['change'] is not None:text+=f"؛ تغییر نسبت به {row['previous_period']}: {row['change']:+g} "+('واحد درصد' if row['id']=='us-10y' else row['unit'])
        else:text+='؛ مشاهدهٔ قبلیِ قابل مقایسه موجود نیست.'
        lines.append(text)
    if not drivers:lines.append('عدد تازهٔ معتبر برای مقایسهٔ بازار موجود نیست؛ عدد یا جهت قیمت ساخته نشد.')
    available=[r['id'] for r in evidence['public_sources'] if r['status']=='available']
    lines.append('منابع قابل دریافت در این بررسی: '+('، '.join(available) if available else 'هیچ‌کدام'))
    lines.append(framework.get('summary_fa','چارچوب سناریو نیازمند دادهٔ قابل ارجاع است.'))
    lines+=['سناریوی قیمت طلا در دو ساعت و هفت روز: جهت نامشخص است؛ تغییر نفت یا نرخ اوراق به‌تنهایی رابطهٔ علّی یا جهت طلا را اثبات نمی‌کند.',
            'شرط بازبینی: تغییر دادهٔ پیشران، تعارض منابع، پایان اعتبار داده یا ورود شاهد تازه؛ سناریوها و علت تغییر در چارچوب ضمیمه ثبت می‌شوند.',
            'این گزارش تحلیل واقعیِ دادهٔ موجود است؛ مدل پیش‌بینیِ اعتبارسنجی‌شده یا دقت ۸۸–۸۹ درصد را ادعا نمی‌کند.']
    neutral={'direction':'neutral','uncertainty':'high','source_ids':[r['id'] for r in drivers][:6]}
    return {'scope':'global','generated_ms':now_ms,'answer':'\n'.join(lines),'evidence':evidence,
            'foresight_framework':framework,'provider':'local-public-evidence','external_data_sent':False,
            'research_kind':'factual-comparison-and-conditional-scenarios','data_sufficient_for_direction':False,
            'analysis_version':policy_version(),'facts_fingerprint':evidence_fingerprint(evidence),'decision_signal':{'schema':1,'symbol':'XAUUSD','horizon_ms':HORIZON_MS,
                'short_term':neutral,'long_term':dict(neutral)},'can_execute':False,'validated_forecast':False,'calibrated_accuracy_percent':None}


def iran_report(statistics,now_ms):
    from .iran_research import context
    evidence=context(statistics,now_ms)
    rows=evidence.get('observations',[])
    lines=['گزارش آماری ایران، محاسبه‌شده در همین دستگاه؛ مستقل از تصمیم معامله.',
           'زمان دریافت تازه، به معنی دورهٔ آماری تازه یا تأیید زمان انتشار نیست.']
    by_metric={}
    for row in rows:by_metric.setdefault(row.get('metric'),[]).append(row)
    comparisons=[];derived=[]
    for metric,group in by_metric.items():
        group=sorted(group,key=lambda r:str(r.get('period','')),reverse=True)
        latest=group[0]
        lines.append(f"{latest['title']}: {latest['value']} {latest['unit']}؛ دوره {latest['period']}؛ کیفیت {latest.get('quality','نامعلوم')}.")
        if len(group)<2:continue
        prior=group[1]
        if latest.get('calendar')==prior.get('calendar') and latest.get('unit')==prior.get('unit'):
            try:
                months=_month_ordinal(latest['period'])-_month_ordinal(prior['period'])
                if metric in ('inflation_monthly','inflation_yoy','inflation_12m') and months==1:
                    change=latest['value']-prior['value']
                    comparisons.append({'metric':metric,'period':latest['period'],'previous_period':prior['period'],
                        'absolute_change':change,'unit':'واحد درصد؛ تغییر نرخ، نه نرخ تورم جدید','source_url':latest['source_url']})
                    lines.append(f"تغییر این نرخ نسبت به دورهٔ قبل: {change:+.4f} واحد درصد؛ این مقدار نرخ تورم تازه نیست.")
                if metric in ('liquidity','monetary_base') and months==12 and prior['value']>0:
                    growth=100*(latest['value']/prior['value']-1)
                    derived.append({'metric':metric+'_same_month_yoy_growth','period':latest['period'],'previous_period':prior['period'],
                        'value':growth,'unit':'درصد تغییر مانده نسبت به ماه مشابه سال قبل','source_url':latest['source_url'],
                        'not_current_month':True})
                    lines.append(f"تغییر مانده نسبت به همان ماه سال قبل: {growth:+.4f}٪؛ دورهٔ فایل منتشرشده است و آمار ماه جاری محسوب نمی‌شود.")
            except (ValueError,TypeError,KeyError):pass
        if metric=='cpi_index' and latest.get('calendar')==prior.get('calendar') and latest.get('unit')==prior.get('unit'):
            try:
                if _month_ordinal(latest['period'])-_month_ordinal(prior['period'])==1 and latest['value']>0 and prior['value']>0:
                    value=100*(prior['value']/latest['value']-1)
                    derived.append({'metric':'fixed_basket_money_value_change','period':latest['period'],'previous_period':prior['period'],
                        'value':value,'unit':'درصد قدرت خرید مبلغ اسمی ثابت در سبد CPI ملی','source_metric':'cpi_index',
                        'formula':'100 * (previous_cpi / current_cpi - 1)','source_url':latest['source_url'],
                        'not_household_real_income':True,'not_foreign_exchange_rate':True})
                    lines.append(f"تغییر قدرت خرید یک مبلغ اسمی ثابت در همان سبد ملی CPI نسبت به ماه قبل: {value:+.4f}٪. این محاسبهٔ سبد ثابت است؛ درآمد واقعی خانوار یا کاهش ارزش در برابر ارز خارجی را اندازه نمی‌گیرد.")
            except (ValueError,TypeError,KeyError):pass
        # Do not compare Jalali monthly strings or incomparable statistical units.
        if latest.get('frequency')!='annual' or prior.get('unit')!=latest.get('unit') or prior.get('calendar')!=latest.get('calendar'):continue
        try:
            if int(latest['period'])-int(prior['period'])!=1:continue
            change=latest['value']-prior['value']
            if not _valid_number(change):continue
            comparison={'metric':metric,'period':latest['period'],'previous_period':prior['period'],
                        'absolute_change':change,'unit':latest['unit'],'source_url':latest['source_url']}
            if metric in ('broad_money_annual','official_fx_annual') and prior['value']>0:
                comparison['relative_change_percent']=100*change/prior['value']
            if metric.startswith('household_') and prior['value']>0:
                comparison['relative_change_percent']=100*change/prior['value']
                comparison['change_is_nominal_not_real_income']=True
                lines.append(f"درصد تغییر اسمی نسبت به سال قبل: {comparison['relative_change_percent']:+.4f}٪؛ تعدیل تورم نشده و تغییر درآمد واقعی نیست.")
            comparisons.append(comparison)
            lines.append(f"تغییر عددی نسبت به {prior['period']}: {change:+g} {latest['unit']}؛ این تغییر به‌تنهایی سناریوی آینده یا افت قدرت خرید خانوار نیست.")
        except (KeyError,TypeError,ValueError):continue
    if not rows:lines.append('دادهٔ معتبر قابل محاسبه دریافت نشده است؛ هیچ مقدار جایگزین یا صفر ساخته نشد.')
    lines.append('کمبودهای داده: '+ '؛ '.join(evidence.get('missing_topics',[])))
    lines.append('کوتاه‌مدت: مقایسهٔ آمار دریافت‌شده، پیش‌بینی عددیِ اعتبارسنجی‌شده نیست. بلندمدت: دورهٔ هر سری و تأخیر انتشار باید جدا بررسی شود؛ سری سالانه جای دادهٔ جاری را نمی‌گیرد.')
    return {'scope':'iran-statistics-only','generated_ms':now_ms,'answer':'\n'.join(lines),'evidence':evidence,
            'comparisons':comparisons,'derived_statistics':derived,'provider':'local-public-evidence','external_data_sent':False,
            'research_kind':'observed-statistical-comparison','can_execute':False,'used_for_trading':False,
            'validated_forecast':False,'calibrated_accuracy_percent':None}


def persist(store,report,select=True):
    scope=report.get('scope','global')
    states={'local_public_report' if scope=='global' else 'iran_local_report':report}
    if scope=='global' and select:states['amin_economic_calendar']=report
    store.transaction('local_research_report',{'scope':scope,'generated_ms':report['generated_ms'],
        'provider':report['provider'],'external_data_sent':False},states=states,research_report=report)
    return report
