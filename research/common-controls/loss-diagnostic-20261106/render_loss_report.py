"""Render Persian report solely from already computed aggregates."""
import json
from decimal import Decimal as D
from pathlib import Path
root=Path(__file__).resolve().parent
s=json.loads((root/'results/loss-diagnostic-results.json').read_text())
ms=s['metrics']
def f(v,n=2):return format(D(str(v)),f'.{n}f')
def pct(v):return f(D(v)*100)
def short(c):return c.replace('-1.5','')
def tab(h,rows):return '\n'.join(['|'+'|'.join(h)+'|','|'+'|'.join(['---']*len(h))+'|']+['|'+'|'.join(map(str,r))+'|' for r in rows])
def group(m,d,k):return next((g for g in m['grouped_descriptive'] if g['dimension']==d and g['label']==k),None)
out=['# تشخیص زیان و تصمیم شش روش FF — ۶ نوامبر ۲۰۲۶',
"""**صفر روش تأییدشده؛ تصمیم هر شش پیکربندی FF فعلی STOP است.** توقف ارتقای همین پیکربندی ثابت است، نه حکم درباره همه ایده‌های راهبردی آینده.

این تحویل تحلیل واقعی trace موجود طبق PR32#issuecomment-6682894835 است؛ FF سالانه دوباره replay نشد، داده/موتور/پارامتر تغییر نکرد. همه پول‌ها USD سناریویی و زمان‌ها برچسب خام‌اند، نه UTC یا تهران. خروجی معامله بروکر یا سودآوری اثبات‌شده نیست.

## معیار تصمیم

diagnostic-protocol.json پیش از تشخیص جزئی ثبت شد؛ خلاصه منفی قبلی از قبل معلوم بود. این rubric تصمیم گذشته‌نگر است، نه پیش‌ثبت استراتژی پیش از مشاهده سال. STOP: در هر دو هزینه known-partial منفی، جمع قطعه‌های کاملاً حل‌شده منفی و PF بسته زیر۱. CANDIDATE_FOR_FRESH_TEST: همان سه معیار مثبت/بالاتر۱ در هر دو هزینه و صفر unresolved؛ سایر حالت‌ها RESEARCH_ONLY. این قاعده تصمیم مهندسی این مأموریت است، نه آزمون آماری عام.

شش ورود و stop اصلی حفظ شده، اما FF دارای overlay ثابت lot=.01، target distance=10 و horizon=12 کندل است؛ auto-sizing/learning/adaptive exit ربات اصلی این مطالعه نیستند. identity ثابت: 36dd53f0cee311b12cdf00b4133efd87537778d55b63f0faefdc4b2c5b7603db.

## جدول نتیجه

known-partial همه معاملات بسته از جمله prefix قطعه نامعلوم است؛ جمع قطعه کامل فقط قطعه‌های بدون unresolved را شامل می‌شود. هر دو در تمام روش‌ها منفی‌اند. net کامل هر۱۲حالت=None، محدوده unresolved=NOT_BOUNDED. دو هزینه نمونه مستقل بازار نیستند.""",
tab(['روش','هزینه','ورود','بسته','نامعلوم (%)','known-partial','جمع قطعه کامل','PF','تصمیم'],[
[short(m['candidate']),m['cost'],m['positions'],m['resolved'],f"{m['unresolved']} ({pct(m['unresolved_share'])}%)",f(m['known_partial_net']),f(m['fully_resolved_segment_net']),f(m['profit_factor'],3),'STOP'] for m in ms]),
"""## علت قابل‌اندازه‌گیری زیان

این انتساب حسابداری تحت موتور ثابت است، نه شناسایی علت علّی edge بازار. جمع سود مثبت + جمع زیان منفی = known-partial. در breakout/retest بردهای نسبتاً زیاد با باخت‌های بزرگ‌تر خنثی شده‌اند؛ در rejection نرخ برد برای جبران زیان‌ها کافی نیست. علت را صرفاً به gap یا کمیسیون نسبت نمی‌دهیم.""",
tab(['روش','هزینه','برد/باخت/صفر','برد٪ بسته','میانگین برد','قدر مطلق میانگین باخت','جمع برد','جمع زیان'],[
[short(m['candidate']),m['cost'],f"{m['wins']}/{m['losses']}/{m['breakeven']}",pct(m['win_rate_resolved']),f(m['mean_win']),f(m['mean_loss_magnitude']),f(m['positive_net_sum']),f(m['negative_net_sum'])] for m in ms]),
"""هدف ثابت و stop اصلی متغیر است؛ نامتقارنی payout در trace دیده می‌شود. نمونه breakout-20 پایه: برد متوسط۹٫۶۶، باخت۱۴٫۰۶، PF۰٫۸۹۴ با نرخ برد۵۶٫۴۹٪. ریسک اولیه محاسبه‌شده از entry/initial_stop/lots در همین روش میانه۱۴٫۲۰ و حداکثر۹۶٫۰۹ USD است. این قرینه ناسازگاری احتمالی overlay هدف ثابت با ریسک متغیر است؛ خروج جایگزین آزموده نشده و ریسک اولیه حد تضمین‌شده زیان واقعی نیست.

خروج‌های بسته با سهم PnL هر علت در جدول زیر آمده؛ TP_AT_OPEN در TP جمع شده است."""]
rows=[]
for m in ms:
    sl=group(m,'exit_reason','STOP');tp=[g for g in m['grouped_descriptive'] if g['dimension']=='exit_reason' and g['label'] in ['TARGET','TARGET_AT_OPEN_CAPPED']];h=group(m,'exit_reason','MAX_HOLD_CLOSE_ASSUMED')
    rows.append([short(m['candidate']),m['cost'],sl['positions'] if sl else 0,f(sl['known_partial_net']) if sl else '0',sum(g['positions'] for g in tp),f(sum((D(g['known_partial_net']) for g in tp),D(0))),h['positions'] if h else 0,f(h['known_partial_net']) if h else '0'])
out += [tab(['روش','هزینه','SL تعداد','SL net','TP تعداد','TP net','افق تعداد','افق net'],rows),
"""خروج افق close فرضی ثبت‌شده در موتور است، نه معامله واقعی. family/lookback/stop_multiple و جهت در trace وجود دارند و تفکیک شده‌اند؛ ATR/ADX/regime/قدرت سیگنال ذخیره نشده: UNMEASURABLE. توزیع PnL بسته، چارک‌ها، زمان مشاهده و ریسک اولیه در JSON آمده است.

## سوگیری gap و unresolved

هر قطعه مستقل از FLAT شروع شده و بعد از unresolved همان قطعه ورود تازه ندارد؛ تعداد ورودی سانسورشده و جمع قطعه‌ها equity پیوسته نیست. انتخاب فقط قطعه کامل نیز outcome-dependent است؛ اینجا فقط حساسیت را نشان می‌دهد، نه مجوز حذف معامله بد.""",
tab(['روش','هزینه','واجد/skip','قطعه کامل','بدون پوزیشن','قطعه نامعلوم','net بسته prefix نامعلوم','بدترین DD قطعه کامل','بیشترین DD prefix بسته'],[
[short(m['candidate']),m['cost'],f"{m['eligible_segments']}/{m['skipped_segments']}",m['fully_resolved_segments'],m['zero_position_segments'],m['unresolved_segments'],f(m['resolved_prefix_in_unresolved_segments_net']),f(m['worst_closed_dd_fully_resolved_segment']),f(m['worst_observed_closed_prefix_dd'])] for m in ms]),
"""قطعه بدون پوزیشن زیرمجموعه قطعه کامل با net صفر است؛ شاهد صفر بودن پوزیشن نامعلوم نیست. DDها فقط روی بسته‌های همان قطعه/prefix هستند؛ DD کامل سال و mark-to-market=UNMEASURABLE.""",
tab(['روش','هزینه','rollover نامعلوم','SL/TP مبهم','مرز بدون خروج'],[
[short(m['candidate']),m['cost'],m['unresolved_reasons'].get('ROLLOVER_COST_UNKNOWN',0),m['unresolved_reasons'].get('AMBIGUOUS_SL_TP',0),m['unresolved_reasons'].get('UNRESOLVED_BOUNDARY',0)] for m in ms]),
"""دو سناریو برای QA مجموعاً۴۱۵ رکورد نامعلوم دارند:۳۴۱rollover،۷۰مبهم و۴مرز؛ اینها معاملات مستقل بیشتر نیستند. exit_time نامعلوم پایان مشاهده است، نه خروج اجراشده. stop/target/initial risk در نبود quote اجرایی و swap، حد واقعی PnL نیستند؛ هیچ best/worst یا net=0 ساخته نشد: NOT_BOUNDED.

## هزینه و تغییر مسیر

base: spread=.30،slippage=.10 هرسمت،commission=0 USD/lot roundtrip؛ envelope:.50،.20 و10. همه فرض‌اند. gross موتور قبلاً spread/slippage را در fill دارد؛ دوباره کم‌کردنشان اشتباه است. اجزای نقدی جداگانه spread/slippage ثبت نشده: UNMEASURABLE. کمیسیون سناریویی از gross-net دقیقاً بازتطبیق شد.""",
tab(['روش','کمیسیون base/env بسته','ورود مشترک','فقط base/env','زمان خروج متفاوت','net جفت بسته env-base'],[
[short(c['candidate']),'/'.join(f(next(m for m in ms if m['candidate']==c['candidate'] and m['cost']==co)['commission_from_trace_difference']) for co in ['base','envelope']),c['entry_matched'],f"{c['base_only']}/{c['envelope_only']}",c['paired_exit_time_changed'],f(c['paired_net_delta_envelope_minus_base'])] for c in s['cost_comparisons']]),
"""تطبیق ورود بر segment/side/entry_time است، نه شماره ترتیبی. هزینه بالاتر مسیر خروج و ورودی بعدی را هم عوض می‌کند؛ اختلاف کل net هزینه خالص نیست. حتی جفت مشترک همیشه exit path ثابت ندارد. تغییر status/علت خروج در خلاصه آمده است. replay بدون هزینه اجرا نشده و سهم علّی خالص spread/slippage ادعا نمی‌شود.

## زمان‌های آسیب‌پذیر، توصیفی

همه برچسب‌ها خام‌اند. نزدیک gap یعنی ورود حداکثر۶۰دقیقه پیش از gap بعدی؛ نزدیک نامزدتعطیلی یعنی فاصله تا۲۴ساعت از یکی از۱۱gap نامزد قبلی، نه تعطیلی رسمی. آمار همه ماه‌ها/ساعت‌ها/روز هفته/جهت در raw-time-cohorts.json و همه روزها در daily-cohorts.json است؛ fit یا فیلتر معامله انجام نشد."""]
rows=[]
for m in ms:
    n=group(m,'near_next_gap_60m','True') or dict(positions=0,unresolved=0,known_partial_net='0')
    h=group(m,'near_holiday_candidate_gap_24h','True') or dict(positions=0,unresolved=0,known_partial_net='0')
    rows.append([short(m['candidate']),m['cost'],f"{n['unresolved']}/{n['positions']}",f(n['known_partial_net']),f"{h['unresolved']}/{h['positions']}",f(h['known_partial_net']),f"{m['monthly_positive_known_partial']}/{m['monthly_negative_known_partial']}"])
out += [tab(['روش','هزینه','نامعلوم/ورود نزدیکgap','net جزئی نزدیکgap','نامعلوم/ورود نامزدتعطیلی','net جزئی نامزدتعطیلی','ماه مثبت/منفی جزئی'],rows),
"""مثلاً breakout-20 پایه نزدیک gap،۳۲از۴۳ورود نامعلوم و net بسته باقی‌مانده+۸۳٫۸۳ دارد؛ این سود کامل گروه نیست. این نمونه خطر survivor selection را نشان می‌دهد؛ گروه prefix مثبت را ساعت سودآور نمی‌نامیم.

بدترین ساعت/روز خام در envelope از نظر known-partial با اندازه نمونه؛ این extrema پس از مشاهده گزارش شده و پیشنهاد فیلتر یا نتیجه تأییدی نیست:"""]
rows=[]
for m in ms:
    if m['cost']!='envelope':continue
    h=min((g for g in m['grouped_descriptive'] if g['dimension']=='hour'),key=lambda g:D(g['known_partial_net']))
    d=min((g for g in m['grouped_descriptive'] if g['dimension']=='day'),key=lambda g:D(g['known_partial_net']))
    rows.append([short(m['candidate']),h['label'],f(h['known_partial_net']),f"{h['positions']}/{h['unresolved']}",d['label'],f(d['known_partial_net']),f"{d['positions']}/{d['unresolved']}"])
out += [tab(['روش','ساعت خام','net جزئی ساعت','ورود/نامعلوم','روز خام','net جزئی روز','ورود/نامعلوم'],rows),
"""## کیفیت کنترل و رسید

۷٬۲۷۸ بسته با Decimal از fill ثبت‌شده و کمیسیون سیاست ثابت بازتطبیق شد؛۴۱۵ نامعلوم فاقد exit/gross/net ساختگی کنترل شد.۳٬۱۰۸سلول اجرا و۲۴skip، digest trace، identity شامل policy/selection/code/manifest، hash شش فایل کد، آمار جدول/summary، برد/باخت و DD قطعه کامل تطبیق شد.۷آزمون محاسبات تشخیص PASS؛ هیچ‌یک replay تازه سال نیست.

کنترل اولیه یک عدم‌تطبیق واقعی یافت: original_summary_sha256 جدول قدیمی d0d79c04… با byte hash خلاصه فعلی 3ba733c7… برابر نیست. JSON خلاصه محلی با remote PR32 دقیقاً برابر است؛ عددهای جدول/by-segment/trace مستقل تطبیق شدند. پیوند byte hash قدیمی همچنان تأییدنشده است؛ اصل فایل و hash ادعایی بازنویسی نشد. این مدرک دستکاری نیست. رسید جدید hash ورودی واقعی و خروجی و کد را ثبت می‌کند.

صحت حسابداری، صحت اقتصادی fill/BidAsk/ساعت/هزینه/swap تاریخی را ثابت نمی‌کند؛ آن مدارک ناکافی‌اند. توزیع ویژگی‌های موجود توصیفی است و برای شرایط ذخیره‌نشده UNMEASURABLE حفظ شد.

## تصمیم و ادامه

STOP برای هر۶پیکربندی فعلی؛ RESEARCH_ONLY=۰،CANDIDATE_FOR_FRESH_TEST=۰ در rubric حاضر؛ صفر روش تأییدشده. پارامتر برای سود مثبت همین سال تغییر نمی‌کند. فرضیه ابزارگذاری بدون تغییر جریان معامله در RESEARCH_HYPOTHESIS_FA.md ثبت شده و ادعای سود ندارد؛ NO_FRESH_HOLDOUT. آزمون آینده اجرا نشده است.

بازیابی M5 PR34 بسته است:۰از۱۱٬۳۹۷؛ علت اختصاصی feed Eplanet UNKNOWN. یادداشت بعدی PR34 درباره CME outage/Memorial Day صرفاً قرینه تاریخی است و علت Eplanet فرض نشده. دانلود، تیکت یا قیمت‌سازی تازه انجام نشد.

فقط آمار و hash منتشر می‌شوند؛ trace/قیمت/اکانت خصوصی مانده‌اند. هیچ MT5/order_check/معامله/نصب/تغییر main یا ربات/Merge/پرداخت/توقف آرتین انجام نشد.

بازتولید با Python استاندارد: loss_diagnostic.py، آرگومان‌های --source پوشه شواهد FF، --trace-dir پوشه خصوصی، --protocol diagnostic-protocol.json، --out پوشه خروجی. کد فقط aggregate می‌کند و engine/strategy/MT5 import ندارد. diagnostic-receipt.json رسید اجرا و loss-diagnostic-summary.json خلاصه عددی است."""]
(root/'LOSS_DIAGNOSIS_DECISION_FA.md').write_text('\n\n'.join(out)+'\n',encoding='utf-8')
print('REPORT_WRITTEN')
