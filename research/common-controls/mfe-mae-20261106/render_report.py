"""Report rendering of existing excursion aggregates; no strategy execution."""
import json
from decimal import Decimal as D
from pathlib import Path
root=Path(__file__).resolve().parent
s=json.loads((root/'results/mfe-mae-results.json').read_text())
allrows=[r for r in s['metrics'] if r['period_raw']=='ALL']
def f(x,n=3):return '—' if x is None else format(D(str(x)),f'.{n}f')
def short(x):return x.replace('-1.5','')
def table(h,rows):return '\n'.join(['|'+'|'.join(h)+'|','|'+'|'.join(['---']*len(h))+'|']+['|'+'|'.join(map(str,r))+'|' for r in rows])
out=['# فراز: MFE/MAE، تناسب ریسک و هدف و پروتکل آزمون آینده — ۶ نوامبر ۲۰۲۶',
"""**تناسب نامتوازن هدف ثابت با ریسک اولیه در breakout/retest مشاهده می‌شود؛ سودآوری هیچ راهبرد جدیدی هنوز آزموده یا تأیید نشده است.** هر شش FF قدیمی STOP می‌مانند. این مرحله با raw و trace موجود، بدون اتصال MT5، دریافت داده، اجرای signal engine یا تغییر پارامتر انجام شد.

دستور PR32#issuecomment-6683758490 مبناست. وضعیت همه تحلیل‌ها EXPLORATORY / IN_SAMPLE و NO_FRESH_HOLDOUT است. اعداد، داده واقعی OHLC تحت فرض‌های هزینهٔ ثابت‌اند؛ معامله و quote اجرایی واقعی بروکر نیستند.

## موجودی و کفایت داده

۲۰ جفت CSV/باینری M15 اصلی با manifest/hash دوباره تأیید شد:۲۳٬۶۴۳کندل از2025-11-05 11:00تا2026-11-05 10:45برچسب خام؛۳۵٬۰۴۰جایگاه تقویمی،۱۱٬۳۹۷غایب،۲۶۰gap و۲۶۱قطعه. طول میانه/بیشینه قطعه۹۲کندل و کمینه۱است. غیبت تقویمی به معنی معامله ازدست‌رفته یا تعطیلی رسمی نیست.

دریافت جدید۲۳٬۷۳۵M15در cache موجود و hashCSV آن ثبت شد؛ به trace FF یا پنجره‌ها مخلوط نشد. نمونه قدیمی فقط۱۰۴کندل یکتا از۱۳بازه مرزی وکنترل است؛ یک سال یا دوره ارزیابی معاملاتی نیست.

پوشش ماهانه منبع اصلی (برچسب خام، ماه‌های ابتدا/انتها ناقص):""",
table(['ماه خام','M15 موجود'],sorted(s['inventory']['monthly_bar_counts'].items())),
"""BID بر مبنای شواهد chart_mode و تطبیق feed قبلی پشتیبانی می‌شود؛ Ask و هزینه/swap تاریخی کافی نیست. UTC/DST و تقویم تاریخی سشن مستقل تأیید نشده‌اند. برای اکتشاف فعلی داده کافی است؛ برای سود سالانه کامل، اجرای پیوسته و تکرارپذیری مستقل کافی نیست.

## تعریف سنجه‌ها و کنترل ابهام

دو تحلیل جدا وجود دارد:

۱. رفتار فرضی۱۲کندل پس از ورود ثبت‌شده: هر۱۲کندل باید متوالی موجود و بدون عبور از gap یا پایان روز خام باشند. ممکن است پس از خروج اصلی ادامه یابد؛ MFE/MAE این پنجره، excursion طول عمر معامله نیست و بازده راهبرد تازه محسوب نمی‌شود.

۲. طول عمر معامله حل‌شده: extrema کندل خروج ممکن است پس از خروج رخ داده باشد. کران پایین MFE/MAE از کندل‌های قطعاً پیش از کندل خروج و netخروج ثبت‌شده، و پوش بالایی با افزودن extrema کندل خروج محاسبه شد. پوش بالایی فرصت قطعیِ قابل معامله نیست. برای unresolved، excursion دقیق طول عمر و PnLکامل ساخته نشد.

liquidation فرضی از BID، Ask-shift برای short، لغزش نامطلوب خروج و کمیسیون roundtrip همان سیاست ثابت استفاده می‌کند؛ ورود ثبت‌شده قبلاً هزینه سمت ورود را دارد و دوباره کسر نشد. MFE=max(0,max net)،MAE=max(0,-min net). R=فاصله entryتاinitial_stop×contract100×lotاست؛ swap/زیان دنباله‌دار تضمین‌شده را پوشش نمی‌دهد.

هدف nominal ثابت فاصله قیمتی۱۰ دارد؛ درlot=.01 وcontract100معادل۱۰USD پیش از هزینه خروج است، نه۱۰USD سود خالص تضمین‌شده. در base spread=.30/slippage=.10/commission0 و در envelope .50/.20/10USDperlotفرض شده‌اند.

## آیا هدف با stop متغیر mismatch دارد؟
""",
table(['روش','هزینه','ورود trace','میانه ریسک اولیه USD','میانه هدف اسمی/R','هدف زیر1R (تعداد/درصد)'],[
[short(r['candidate']),r['cost'],r['entries'],f(r['initial_risk_usd']['median'],2),f(r['nominal_target_R']['median']),f"{r['target_below_1R_count']} / {f(D(r['target_below_1R_count'])*100/r['entries'],2)}%"] for r in allrows]),
"""پاسخ برای breakout/retest مثبت است: اکثریت هدفی زیر۱Rدارند. اما rejection با میانه هدف بیش از۱Rهم در گزارش قبلی زیان‌ده بود؛ بنابراین هدف ثابت تنها علت ممکن شکست نیست. ریسک بزرگ‌تر از هدف، به‌تنهایی اثبات نمی‌کند که هدف۱٫۵Rسودده می‌شود؛ آن فرضیه هنوز اجرا نشده است.

## توزیع رفتار۱۲کندل بعد از ورود
"""]
out.append(table(['روش','هزینه','پنجره کامل','رد gap/ناقص','رد مرز روز خام','MFE میانهR','MAE میانهR','MFE≥1R','MAE≥1R'],[
[short(r['candidate']),r['cost'],r['forward_eligibility'].get('ELIGIBLE',0),r['forward_eligibility'].get('INCOMPLETE_OR_GAP',0),r['forward_eligibility'].get('RAW_DAY_BOUNDARY',0),f(r['mfe12_R']['median']),f(r['mae12_R']['median']),r['full12_mfe_at_least_1R'],r['full12_mae_at_least_1R']] for r in allrows]))
eligible=sum(r['forward_eligibility'].get('ELIGIBLE',0) for r in allrows)
gap=sum(r['forward_eligibility'].get('INCOMPLETE_OR_GAP',0) for r in allrows)
day=sum(r['forward_eligibility'].get('RAW_DAY_BOUNDARY',0) for r in allrows)
out.append(f"""از{s['entries_from_trace']}رکورد دو سناریو،{eligible}پنجره۱۲کندلی واجد،{gap}ناقص/دارایgap و{day}مرزروزخام بودند. اینها نمونه‌های مستقل بیشتر نیستند؛ روش‌ها و هزینه‌ها می‌توانند همان کندل‌ها و ورودها را به اشتراک بگذارند. تعداد entry-event یکتا با کلید candidate/segment/time در دو هزینه={s['unique_entry_events_across_costs']}است و حتی آنها هم استقلال آماری تضمین‌شده ندارند.

MAEبالاتر از۱R در پنجره۱۲کندلی می‌تواند پس از stop/outcomeاصلی رخ داده باشد؛ آن را زیان تحقق‌یافته پس از stop نمی‌نامیم. دامنه حرکت مطلوب بالا به‌تنهایی به معنی در دسترس بودن سود پیش از stop نیست. اولین برخورد کنترل شد:""")
out.append(table(['روش','هزینه','SL نخست','TP نخست','مبهم هم‌بار','بدون برخورد در12'],[
[short(r['candidate']),r['cost'],r['full12_first_touch'].get('STOP',0)+r['full12_first_touch'].get('STOP_OPEN',0),r['full12_first_touch'].get('TARGET',0)+r['full12_first_touch'].get('TARGET_OPEN',0),r['full12_first_touch'].get('AMBIGUOUS',0),r['full12_first_touch'].get('NO_TOUCH_IN_12',0)] for r in allrows]))
out.append("""در برخورد SL/TPهمزمان، AMBIGUOUSحفظ شد؛ اگر openمشاهده‌شده از قبل یکی از حدود را رد کرده بود، همان برخورد open مقدم بود. شمارش مستقل first-touch با price_exit_reasonموجود trace **صفر مغایرت** داشت. این کنترل روی ورودهای ثبت‌شده است؛ سیگنال یا شش FF دوباره تولید/replay نشد.

## طول عمر واقعیِ ثبت‌شده، با پوش عدم قطعیت کندل خروج
""")
out.append(table(['روش','هزینه','بسته دارای کران','میانه MFE پایینR','میانه پوش MFEبالاR','میانه MAEپایینR','میانه پوش MAEبالاR','unresolvedجدا'],[
[short(r['candidate']),r['cost'],r['lifetime_bounds_count'],f(r['life_mfe_lower_R']['median']),f(r['life_mfe_upper_R']['median']),f(r['life_mae_lower_R']['median']),f(r['life_mae_upper_R']['median']),r['source_unresolved']] for r in allrows]))
out.append("""کران‌ها مشروط به fill و هزینه سناریویی trace هستند؛ کران اجرای واقعی بروکر نیستند. همه۷٬۲۷۸مورد بستهٔ دو سناریو پوش داشتند؛۴۱۵unresolvedجدا و PnLشان NOT_BOUNDEDماند. این عدد QAدو سناریو است، نه تعداد معاملات واقعی یا مستقل.

## توزیع دوره‌ای؛ نه تکرارپذیری بیرون نمونه

فایل mfe-mae-periods.json برای همه ماه‌ها و فصل‌های raw، تعداد ورود/نامعلوم، eligibility، چارک‌های MFE/MAE وtargetR وکران‌های طول عمر را دارد. خلاصهٔ زیر میانه MFE/MAE_R در هزینه envelope و پنجره کامل۱۲کندلی است. فصل اول/آخر ناقص‌اند؛ هیچ دوره holdoutکور یا نمونه مستقل تازه نیست.
""")
quarters=sorted({r['period_raw'] for r in s['metrics'] if '-Q' in r['period_raw']})
rows=[]
for c in sorted({r['candidate'] for r in allrows}):
    cells=[]
    for q in quarters:
        r=next((r for r in s['metrics'] if r['candidate']==c and r['cost']=='envelope' and r['period_raw']==q),None)
        cells.append('—' if r is None else f"{f(r['mfe12_R']['median'])}/{f(r['mae12_R']['median'])}; n={r['forward_eligibility'].get('ELIGIBLE',0)}")
    rows.append([short(c)]+cells)
out.append(table(['روش']+quarters,rows))
out.append("""تفاوت فصل‌ها توصیفی است و برای انتخاب بهترین فصل/ساعت یا fit استفاده نشد. هیچ سود/درصدبرد تازه یا PFراهبرد جایگزین از MFEمحاسبه نشده است.

## دو فرضیه ثبت‌شده پیش از اجرای آنها

نسخه کامل، پارامتر قفل‌شده، معیار ابطال و پروتکل در hypotheses-and-future-test-protocol.json است؛ هر دو REGISTERED_NOT_EXECUTED و NO_FRESH_HOLDOUT:

|فرضیه|تغییر مشخص|کنترل و مانع|
|---|---|---|
|H1_RISK_LINKED_TARGET_1P5R|هدف دقیق۱٫۵برابر فاصلهentryتاstop؛ horizon12، ورود/stopثابت|برای نسبت‌دادن اثر، sizingoverlayبرابر در baseline و ablation؛ هیچ جستجوی چند ضریب|
|H2_PREDECLARED_SESSION_FLAT|عدم ورود وقتی horizon12پیش از تعطیلیِ مستند جا نمی‌شود؛ خروج در آخرین quoteقابل‌اجرا پیش از وقفه|تقویم باید از پیش دانستنی و مستقل باشد؛ نقشهgapآینده فیلتر مجاز نیست؛ بدونquote/scheduleمدرک،رویدادBLOCKED|

بودجه ریسک آینده فقط در آزمایشگاه=min(۰٫۲۵٪equity،سقف قبلاًمجاز)،گردکردن lotبه پایین و skipاگرحداقلlotبودجه را رد کند. فایل عملیاتی/ریسک موجود تغییر نکرد. stop فاصله‌دار در openباquoteنامطلوب و لغزش محاسبه می‌شود؛ capاسمی تضمین hard-lossنیست.

معیار ارتقای پژوهشی پیشنهادی، از پیش برای آزمون آینده: حداقل۱۰۰پوزیشن شبیه‌سازی‌شده حل‌شده در هر دوره مستقل، PFمحافظه‌کارانه>۱٫۱۰،expectancyخالص>۰،DDنسبیMTM≤۶٪،بدترین فصل≥۰،وPnLکامل شناخته‌شده. بدونتقویم/quote/swapیاequityمعلوم،عدم قطعیت باصفرپرنمی‌شود. DDبسته وMTM،ماه وrollingسه‌ماهه،veto/no-trade وتمامunresolvedبایدجداگزارش‌شوند. این معیارهای انتخابی پژوهش‌اند، نه تضمین سود.

سیاست fillBid/Ask،اسپرد/لغزش/کمیسیون دو سناریو،swapنامعلوم،ابهامSL/TP،عدمcarryبهgapوfreezehashهمگی در پروتکلند. هیچ‌یک در این مرحله برای H1/H2اجرا نشده است؛ نتیجه قدیمی به برنده تغییر نام داده نشد.

## موانع و مرحلهٔ دادهٔ جدید

سال۲۰۲۵–۲۰۲۶بارها دیده شده وIN_SAMPLEاست؛۱۰۴کندل قدیمی برایارزیابی مستقل کافی نیستند. اثباتREPLICATED/OUT_OF_SAMPLEهنوزمجازنیست. داده قدیمیِ منظم پس ازکشف، به‌خودی‌خود holdoutکورنیست؛ دوره زمانی واقعاًدست‌نخورده و پروتکل پیشاقفل لازم است.

برای درخواست احتمالی بعدی، فقط برآورد و نه اجرا: M15بازه2024-11-05تا2025-11-05حداکثر۳۵٬۰۴۰جایگاه؛ باrecord۶۰بایتیحدود۲٫۱۰MBباینری،CSVاحتمالاًچندMBتا سقف پیشنهادی۱۰MB. chunk۲۸روزه حدود۱۴درخواست پایه دارد؛ زمان واقعی server/cacheنامعلوم است و برای برنامه‌ریزی باید چنددقیقه با سقف توقف جدا تعریف شود، نه تضمین سرعت نمونه. هیچ اتصال یا دریافت جدید انجام نشد؛ محدوده/زمان/سقف/رفتارretryبایدپیش ازاجراصریحاًتأییدشوند.

## کنترل و نتیجه

۶آزمون متمایزPASS: ابهامهم‌بار،اولویتopenمشاهده‌شده،پوشکندلخروج،عدم‌دوباره‌شماریهزینه،Askدرshortوگیتgap/مرزروز. بازشماری مستقل ۱۲۰ تطبیق شمارش ماه/فصل با کل را تأیید کرد؛ ۶۷۹۵ پنجره واجد،۸۴۰ناقص/گپ،۵۸مرزروزخام و صفر مغایرت first-touch. hashورودی/manifest/trace/selection/policy،کدمحاسبه،پروتکل تحلیل وپروتکل آینده در رسیدند. originalM15/rawتغییرنکرد؛داده entry-levelوOHLCفقطخصوصی،گزارش‌هافقطcount/سنجه/hashاند.

نتیجه مرحله اول: mismatchاندازههدف/ریسکمشاهدهشد،محدودیتترتیبحرکتدرM15وpost-exitبه‌وضوحتفکیکشد،دوفرضیهقابل‌ابطالثبتشد؛**هیچروشسودده یاتکرارپذیرجدیدتأییدنشد**. هرششFFهمچنانSTOP. بدونMT5/order_check/معامله/نصب/mainrobotchange/Merge/هزینه/تیکت/توقفپروژهدیگر.

بازتولید فقط آفلاین: Pythonاستاندارد،mfe_mae_analysis.pyبا مسیرraw-dir/source/trace-dir/prior-dir/new-dirموجود وprotocol/out/private-out؛هیچengine/strategy/MT5importندارد. رسیداجرادرresults/mfe-mae-execution-receipt.jsonاست.
""")
(root/'MFE_MAE_FIRST_STAGE_FA.md').write_text('\n\n'.join(out)+'\n',encoding='utf-8')
print('REPORT_RENDERED')
