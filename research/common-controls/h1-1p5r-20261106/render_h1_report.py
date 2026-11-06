import json
from pathlib import Path
from decimal import Decimal as D
root=Path(__file__).resolve().parent
s=json.loads((root/'results/h1-summary.json').read_text())
segs=[r for r in s['results'] if r['cohort']=='independent_segments']
prefix=[r for r in s['results'] if r['cohort']=='continuous_known_prefix']
dds=json.loads((root/'results/h1-prefix-dd.json').read_text())['metrics']
def f(x,n=2):return 'UNMEASURABLE' if x is None else format(D(str(x)),f'.{n}f')
def pct(x):return f(D(x)*100)
def short(c):return c.replace('-1.5','')
def tab(h,rows):return '\n'.join(['|'+'|'.join(h)+'|','|'+'|'.join(['---']*len(h))+'|']+['|'+'|'.join(map(str,r))+'|' for r in rows])
out=['# آزمون آزمایشگاهی قفل‌شده H1: هدف۱٫۵R — ۶ نوامبر۲۰۲۶',
"""**H1 در این آزمونِ مشترک برای هر شش روش و هر دو هزینه، PFبسته زیر۱ و expectancyبسته منفی داشت؛ هیچ حالت از screeningPF>1.10عبور نکرد.** در rejection زیان کمتر شد، اما مثبت نشد؛ در breakout/retest بدتر شد. شش FFقبلی همچنانSTOP،H2=BLOCKED_SCHEDULE وNO_FRESH_HOLDOUT.

این نتیجه فقط IN_SAMPLE / EXPLORATORY_ONLY است؛ نه سود سالانه کامل،نه اثربخشی مستقل۱٫۵Rدر همه بازارها. گزارش طبق PR32#6683991123 و فرضیه frozen درcommit666b80d0fe7b623afffc1aef402581200064d4b7 تهیه شد.

## قرارداد اجرا و موتور

همان historical_engine.py بدون تغییر،همان تابع اصلی candidate/plan،ورود برکندل بسته،stopاصلی،horizon12 ودوcost استفاده شد. hashموتور و۶فایل اصل مدل/راهبرد/تحلیل/ریسک/sizing/exit باsnapshotFFتطبیق داده شد؛۲۰جفتCSV/binقدیمی،۲۳۶۴۳M15 و۲۶۱قطعه باhashselectionتأیید شدند. هیچ SDK/MT5یا داده جدیدی استفاده نشد.

پیش از اجرای H1،۶fixturePASS و۶۲بازپخش کوچک پوشش‌دهندهٔ علت‌های خروج FFثبت‌شده،باentry/exit/time/reason/netهمانtraceدقیقاًبرابرشدند. موتور سالم بود و نیازی به بازنویسی یا تغییر حساس آن نبود؛ adapterمستقل فقط پارامترtarget_distanceوlotsموجود موتور را برای هرورود فراخوانی کرد.

تنها تفاوت بازوها target است: baseline=فاصله۱۰ازentry،H1=دقیق۱٫۵×abs(entry-initial_stop). stop،entry،side،volume،حالتintrabarوhorizonهرجفت یکسان‌اند؛ هیچ gridsearchیاانتخاب بهترین ماه/ساعت انجام نشد.

## sizing و eligibility مشترک

equityمرجع هرورود،کمترِcashمعلوم دوبازوست؛equityنتیجه آینده پیش ازtimestampخروج ثبت نمی‌شود. بودجه=min(.25%،سقف .5% سیاست آزمایشگاهی قبلی)×equityمرجع است. سقف قبلی ازmanagement-policy.jsonگرفته شد وقراردادliveaccountنیست.

ریسکمحاسباتی lot شامل فاصلهstop،envelopeلغزش.20وکمیسیون10USD/lotاست؛حجمبهگام.01پایینگردومحدودبهحداقل.01،حداکثر10ونسبتnotional2شد. اگرminlotبودجه را رد کرد،هردوبازوvetoشدند. اینcapاسمی تضمین بدترین زیان درgapنیست. مشخصاتlot/tickهمانdefaultsقبلی‌اند،نهگواهی تاریخی‌بروکر.

تنها وقتی هردوبازوflatوequityمعلوم‌اند،همانplanرویhistoryبستهحداکثر120barارزیابیشد. اشغال‌بودن هربازو هردورا منتظرمی‌گذارد. بنابراین cohortمشترک برایانتسابtargetاست؛مسیر مستقل H1یاFFاولیهlot=.01نیست. تغییر حجم/eligibilityنسبتبهFFاولیه آشکار است و سوددوستون را با گزارش قدیمی جمع نمی‌کنیم.

دوخروجی جداست: قطعه‌های مستقل باFLAT/10000صریح درهرقطعه،وprefixپیوستهباcashحمل‌شدهفقطتازمانی‌کههردوبازومعلوم‌اند. بعدازunresolvedدرقطعه ورودی تازه مسدودمی‌شود؛درprefixپیوسته همه قطعه‌های بعدی نیزمسدودند. شروع قطعه مستقل بعدی ادامه equityنامعلوم نیست.

## نتیجه قطعه‌های مستقل

اعداد net فقط جمع معاملات بستهٔ معلوم‌اند؛نهannualnet. تفاوت ستونknown-partialها لزوماًdeltaجفتنیست،چونresolvedبودن دوطرف یکسان نیست. deltaپایین فقط رویجفت‌هایی است کههردوبسته‌اند وsampleselectionخودرا دارد.""",
tab(['روش','cost','ورود مشترک','baseline بسته/نامعلوم','H1 بسته/نامعلوم','baseline known-net','H1 known-net','PF base/H1','delta جفت بسته','جفت بسته/نامعلوم'],[
[short(r['candidate']),r['cost'],r['arms'][0]['entries'],f"{r['arms'][0]['closed']}/{r['arms'][0]['unresolved']}",f"{r['arms'][1]['closed']}/{r['arms'][1]['unresolved']}",f(r['arms'][0]['known_partial_net']),f(r['arms'][1]['known_partial_net']),f"{f(r['arms'][0]['PF'],3)}/{f(r['arms'][1]['PF'],3)}",f(r['matched_delta_H1_minus_baseline']),f"{r['known_matched_pairs']}/{r['pair_unknown_count']}"] for r in segs]),
"""rejectionبهبودنسبیِزیانداشت؛این با سود مثبت برابرنیست. حتیbaselineoverlayret20baseکهknown-netآن+۴٫۵۵وPF≈۱٫۰۰۳است،دارایunresolvedوپایین‌تر ازscreen۱٫۱۰است؛FFاصلی STOP باقی‌می‌ماند.

میانگین/نرخ‌برد وexpectancyخالصِ بخش معلوم H1:""",
tab(['روش','cost','برد٪ بسته H1','میانگین برد','قدر مطلق میانگین باخت','expectancy بسته','ambiguous H1/base','rollover H1/base','boundary H1/base'],[
[short(r['candidate']),r['cost'],pct(r['arms'][1]['win_rate']) if r['arms'][1]['win_rate'] else '0',f(r['arms'][1]['average_win']),f(r['arms'][1]['average_loss']),f(r['arms'][1]['expectancy_known_closed']),
f"{r['arms'][1]['exit_reasons'].get('AMBIGUOUS_SL_TP',0)}/{r['arms'][0]['exit_reasons'].get('AMBIGUOUS_SL_TP',0)}",
f"{r['arms'][1]['exit_reasons'].get('ROLLOVER_COST_UNKNOWN',0)}/{r['arms'][0]['exit_reasons'].get('ROLLOVER_COST_UNKNOWN',0)}",
f"{r['arms'][1]['exit_reasons'].get('UNRESOLVED_BOUNDARY',0)}/{r['arms'][0]['exit_reasons'].get('UNRESOLVED_BOUNDARY',0)}"] for r in segs]),
"""قطعهکاملاًحل‌شدهدرجدولبعدی یعنیهردوبازودرکلقطعهunresolvedنداشتند؛انتخابآنهاoutcome-dependentاست وفقطمقایسهتوصیفی،نهاصلاحانتخابینتیجه. DDبسته وMTMذکرشدهبیشینهٔهمانقطعه‌های مستقل‌اند،نهDDکل‌سال.""",
tab(['روش','cost','قطعه مشترک کامل','net base قطعه کامل','net H1 قطعه کامل','DDبسته بدترین قطعه base/H1 USD','DD نمونهMTM بدترین قطعه base/H1 ٪','کمیسیون بسته base/H1'],[
[short(r['candidate']),r['cost'],r['joint_fully_resolved_segments'],f(r['arms'][0]['joint_fully_resolved_segment_net']),f(r['arms'][1]['joint_fully_resolved_segment_net']),
f"{f(r['arms'][0]['closed_dd_worst_segment_usd'])}/{f(r['arms'][1]['closed_dd_worst_segment_usd'])}",
f"{pct(r['arms'][0]['sampled_mtm_dd_worst_segment_fraction'])}/{pct(r['arms'][1]['sampled_mtm_dd_worst_segment_fraction'])}",
f"{f(r['arms'][0]['commission_closed'])}/{f(r['arms'][1]['commission_closed'])}"] for r in segs]),
"""grossدرموتورشاملspread/slippageداخلfillاست؛کمیسیونازgross-netقابلکنترلاست. جزءنقدیجداگانهspread/slippage=UNMEASURABLEو دوبارهکسرنشد. هزینهتاریخیواقعی/Ask/swapوجودکافیندارند؛base=.30/.10/0وenvelope=.50/.20/10فرضی‌اند.

## veto و قیمت اجرایی
""",
tab(['روش','cost','plan مشاهده‌شده درflat','ردminlot/risk/notional','barمشغول مشترک،نهsignalveto','barمسدود بعدunknown','H1targetخارجtick.01'],[
[short(r['candidate']),r['cost'],r['counters'].get('signals_flat',0),r['counters'].get('MIN_LOT_EXCEEDS_BUDGET_OR_NOTIONAL',0),r['counters'].get('joint_busy_bars',0),r['counters'].get('bars_blocked_after_unknown',0),r['counters'].get('H1_TARGET_OFF_DECLARED_TICK',0)] for r in segs]),
"""target۱٫۵Rدقیقگاهی نیم‌سنتی وخارجtickفرضی.01است؛بدونتغییرپنهانگردنشد. اینمانعاضافیبرایادعایقیمتقابل‌اجرابروکراست. آزموننسخهگردشدهیکتغییرپروتکلجداخواهدبودوایننوبتاجرانشد. ستونbusyتعدادbarاست،نهتعدادسیگنال یا ورود ازدست‌رفته. سایرvetoهاوفیلدهایاصلیدرJSONهستند.

## prefix پیوسته و توقف equity نامعلوم

درتمام۱۲حالتprefixپیوسته دراولینunresolvedمتوقفشد؛هیچequityنامعلومبرایcompoundجایگزیننشد ونتیجهقطعه‌هایبعدیصفرنامیده‌نشد. بعضیprefixهایبسیارکوتاهمثبت‌اند؛انتخابآنهابرایاعلامبرنده مجازنیست.""",
tab(['روش','cost','قطعه پردازش/بعدی مسدود','ورود مشترک prefix','بسته H1','netجزئی base/H1','unresolved base/H1','netسالانه'],[
[short(r['candidate']),r['cost'],f"{r['processed_segments']}/{r['blocked_later_segments']}",r['arms'][1]['entries'],r['arms'][1]['closed'],f"{f(r['arms'][0]['known_partial_net'])}/{f(r['arms'][1]['known_partial_net'])}",f"{r['arms'][0]['unresolved']}/{r['arms'][1]['unresolved']}",'UNKNOWN'] for r in prefix]),
"""DDتجمعیِprefixازtraceذخیره‌شده،بدونreplayمجددبازسازی شد. MTMفقطنمونهopen/closeقابل‌محاسبهباcostفرضی است؛درbarخروجنامعلوم قطعشد. هرarmممکن‌استدرحالی‌کهpeerنامعلوم است،خروجقابل‌مشاهدهبعدیخودرا داشته‌باشد؛هیچورودجدیدی پسازاینعدم‌قطعیت انجامنشد. DDدقیقداخلکندل وDDکل‌سالUNKNOWN/UNMEASURABLEمی‌ماند.""",
tab(['روش','cost','DDبستهprefix base/H1 USD','DDنمونهMTMprefix base/H1٪'],[
[short(r['candidate']),r['cost'],
'/'.join(f(next(d for d in dds if d['candidate']==r['candidate'] and d['cost']==r['cost'] and d['arm']==a)['observed_prefix_closed_dd']['usd']) for a in ['baseline_overlay','H1_1p5R']),
'/'.join(pct(next(d for d in dds if d['candidate']==r['candidate'] and d['cost']==r['cost'] and d['arm']==a)['observed_prefix_sampled_mtm_dd_fraction']) for a in ['baseline_overlay','H1_1p5R'])] for r in prefix]),
"""## کیفیت، پروتکل و تصمیم

۶fixtureآداپترPASS،۶۲paritycheckخروجاصلFFدقیقاًبرابر. QAمستقلtraceهرجفتentry/stop/volumeبرابر،targetدقیق۱٫۵R،بودجهولotrounding،عدمoverlapو توقفprefixراکنترلکرد. جمعQAشامل۶۳۰۳جفتباprefixزیرمطالعه،۱۱۸۵۶cashidentityبسته و۷۵۰unknownبدونexitساختگیبود؛prefixودوسناریوتکرارهمانمنبع‌اند،نهافزایش نمونه‌مستقل. مطالعهقطعه‌های مستقل۶۱۲۷جفتدرهردوهزینهداشت.

فایلh1-locked-policy.jsonقبل ازاجرایH1محلیذخیرهشد؛پارامتر۱٫۵Rازپروتکلمنتشرشدهقبلیبود. تغییرsizing/eligibilityبرایکنترلدوطرفشفافثبتشد،نهبهینه‌سازیپسازنتیجه. SHAکدآداپتر،موتوراصلیبدونتغییر،signalcode،policy/cost،manifest،traceخصوصی وخروجیدررسیداست. جدولماهانههمراه است؛همهperiodهاIN_SAMPLE،بدونانتخابساعت/ماهبرنده.

**H1_SCREEN_FAILED_CURRENT_PAIRED_POLICY** برایهرششروش:PFمحافظه‌کارانه زیر۱،expectancyمنفی،unresolvedو نبودfreshholdout. پایین‌بودنDDدرقطعهکوتاه≠DDسالانهپایین. تمامnetسالانهUNKNOWN،حدPnLنامعلومNOT_BOUNDED. ایننتیجهردهمهکاربردهای۱٫۵Rنیست؛برایهمینentry/stop/horizon/هزینه/eligibilityقفل‌شده،پشتیبانیبرایارتقاپیدانشد. ششFFقبلیSTOPرفعنشد.

H2تاوجودتقویمتاریخیهماننمادوquoteاجرایی BLOCKED_SCHEDULE است واجرانشد. داده۲۰۲۵–۲۶قبلاًدیده‌شده؛NO_FRESH_HOLDOUT. دریافتدورهجدیدیااستراتژی/targetدیگربدون دستورجداانجامنشد.

هیچMT5/SDKجدید،order_check/order_send/معاملهREAL/DEMO،تغییرربات/main/فایلraw،نصب،Merge،هزینهیاتیکتانجامنشد. traceقیمت/اکانتخصوصی است؛فقطکدآفلاین،آماروhashمنتشرشد.

بازتولید:Pythonاستاندارد+h1_lab.pyباsourceموتورپژوهشی،strategy-sourceنسخهفریز،raw-dir/trace-dirمحلی،protocol-dirمرحلهMFE،policyوout/private-out. وابستگیسورسمحلیصریحاست؛فایلهایخصوصیدرمخزننیستند. H1ازموتوربدونتغییراستفادهمی‌کندونصبیااجرامتاتریدرلازمندارد.
"""]
(root/'H1_1P5R_RESULT_FA.md').write_text('\n\n'.join(out)+'\n',encoding='utf-8')
print('H1_REPORT_WRITTEN')
