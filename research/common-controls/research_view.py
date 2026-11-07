"""Persian offline read-only export of sanitized research; no trading UI or API."""
import html,json
from pathlib import Path
from registry import Registry
from research_recovery import history
ROOT=Path(__file__).resolve().parent

def build():
    inventory=json.loads((ROOT/'data-validity-inventory.json').read_text(encoding='utf8'))
    comparison=json.loads((ROOT/'comparison-nov05-sanitized.json').read_text(encoding='utf8'))
    previous=json.loads((ROOT/'stage4-results.json').read_text(encoding='utf8'))
    queue=json.loads((ROOT/'mission-queue.json').read_text(encoding='utf8'))
    rows=history(Registry(ROOT/'selector-research.sqlite'))
    labels={'UNKNOWN':'نامعلوم','CONDITIONAL':'مشروط','BLOCKED':'مسدود','HYPOTHETICAL_SCENARIO_ONLY':'صرفاً سناریوی فرضی','VALID':'سابقه سالم؛ نه تأیید مالی','FAILED':'ناموفق','TAMPERED':'دست‌کاری‌شده','None':'نامعلوم','SPREAD_UNKNOWN':'اسپرد نامعلوم'}
    escape=lambda x:html.escape(labels.get(str(x),str(x)))
    def table(headers,body):return '<table><thead><tr>'+''.join('<th>'+escape(x)+'</th>' for x in headers)+'</tr></thead><tbody>'+''.join('<tr>'+''.join('<td>'+escape(x)+'</td>' for x in row)+'</tr>' for row in body)+'</tbody></table>'
    sections=[('کیفیت و پوشش داده‌ها',table(['منبع','نوع','تعداد ردیف','ساعت','جلسات','اعتبار پژوهش مالی'],[(x['contract']['source'],x['contract']['kind'],x['contract']['rows'],x['contract']['time']['status'],x['contract']['session']['status'],'مسدود') for x in inventory])),
        ('مقایسه واقعی نمونه‌ها با نگاشت مشروط',f'<p>نمونه دوم: {comparison["common_m15"]} کندل؛ میانگین اختلاف مطلق Close: {escape(comparison["metrics"]["close"]["mean_absolute"])} دلار/اونس. داده خام محلی؛ تأیید کل سال نیست.</p>'),
        ('ارزیابی مصنوعی روش‌ها — سابقه مرحله چهارم',table(['شناسه','بدترین سود/زیان خالص فرضی','افت سرمایه سناریویی','وضعیت'],[(x['id'],x['worst_case_net'],x['max_drawdown'],x['status']) for x in previous['ranking']['rows']])),
        ('تاریخچه و قابلیت بازیابی',table(['شناسه آزمایش','وضعیت ثبت','بازیابی سابقه','علت شکست'],[(x['id'][:16],x['state'],'سالم؛ استفاده مجدد فقط با تطبیق کامل نسخه و ورودی' if x['recoverable_result'] else 'خیر',x['failure'] or '—') for x in rows])),
        ('صف مأموریت‌ها',table(['مأموریت','وضعیت','اقدام بعد'],[(x['name'],x['status'],x['next']) for x in queue])),
        ('محدودیت‌های باقی‌مانده','<ul><li>۲۶۰ فاصله و نگاشت تاریخی سال UNKNOWN؛ بک‌تست نهایی مسدود.</li><li>سوآپ تاریخی و مسیر Tick کامل تأیید نشده؛ اعداد سناریویی نرخ واقعی بروکر نیستند.</li><li>هیچ راهبرد سودآور بازار تأیید نشده و هیچ فرمان معامله در این صفحه وجود ندارد.</li><li>خروجی مستقل پژوهشی؛ نسخه نصب‌شده کابین ویندوز یا اندروید تغییر نکرده است.</li><li>فهرست اصلی ۱۱۱ اندیکاتور هنوز بازیابی نشده؛ نمونه‌ها جای آن نیستند.</li></ul>')]
    css=(ROOT/'cabin-report-style.css').read_text(encoding='utf8')
    body=''.join('<section class="card"><h2>'+escape(title)+'</h2><div style="overflow:auto">'+content+'</div></section>' for title,content in sections)
    out='<!doctype html><html lang="fa" dir="rtl"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta http-equiv="Content-Security-Policy" content="default-src \'none\';style-src \'unsafe-inline\'"><title>فراز — گزارش پژوهش قابل بازیابی</title><style>'+css+' html{min-width:0!important;width:100%!important}body{display:block;width:100%!important;min-width:0!important;padding:20px;max-width:1200px;margin:auto}section{width:100%;min-width:0}h2{font-size:22px}table{table-layout:fixed}table{width:100%;border-collapse:collapse}td,th{padding:10px;border-bottom:1px solid #526070;overflow-wrap:anywhere}h1{font-size:26px}</style><h1>فراز — وضعیت پژوهش و بازیابی</h1><p>۵ نوامبر ۲۰۲۶ • مشاهده فقط‌خواندنی آفلاین • سودآوری تأیید نشده</p>'+body+'</html>'
    (ROOT/'research-status-fa.html').write_text(out,encoding='utf8')
    return out
if __name__=='__main__':build()
