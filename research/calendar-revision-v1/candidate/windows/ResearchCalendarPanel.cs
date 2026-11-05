using System.Text.Json.Nodes;
namespace Amin.Owner;
internal sealed class ResearchCalendarPanel : Form
{
    internal ResearchCalendarPanel(OwnerApi api,Font font):this((method,path,body)=>api.Call(method,path,body),font,false) {}
    internal ResearchCalendarPanel(Func<string,string,JsonObject?,Task<JsonObject>> call,Font font,bool reviewOnly) {
        Font=font;RightToLeft=RightToLeft.Yes;BackColor=Color.White;
        var intro=new Label { Dock=DockStyle.Top,Height=100,Padding=new Padding(10),Text="تقویم اقتصادی امین — گزارش مستقل و پیگیری منابع\nفعالیت دوره‌ای در زمان روشن بودن ویندوز؛ گزارش‌ها مستقل از تصمیم معامله‌اند. زمان دریافت با دوره آماری فرق دارد؛ پیش‌بینی معتبر فقط پس از آزمون مستقل." };
        var topic=new ComboBox { Dock=DockStyle.Top,DropDownStyle=ComboBoxStyle.DropDownList };topic.Items.AddRange(["پژوهش اقتصادی و گزارش مستقل","پژوهش آماری ایران"]);topic.SelectedIndex=0;
        var consent=new CheckBox { Dock=DockStyle.Top,Height=48,Text="با ارسال گزیدهٔ منابع عمومی و معرفی آثار به نت‌ارز برای سنجش موافقم؛ اطلاعات حساب ارسال نمی‌شود.",Enabled=!reviewOnly };
        var archives=new ComboBox { Dock=DockStyle.Top,DropDownStyle=ComboBoxStyle.DropDownList };var reports=new List<JsonObject>();JsonObject? current=null;bool filling=false,loading=false;
        var buttons=new FlowLayoutPanel { Dock=DockStyle.Top,Height=100,WrapContents=true,AutoScroll=true };
        var local=new Button { Text="پژوهش محلی؛ بدون ارسال داده",Width=245,Height=38,Enabled=!reviewOnly };
        var synthesize=new Button { Text="سنجش، ثبت و نمایش نتیجه",Width=230,Height=42,Enabled=!reviewOnly };
        var reload=new Button { Text="نمایش آخرین وضعیت و گزارش",Width=240,Height=42 };
        var newer=new Button { Text="گزارش‌های جدیدتر",Width=160,Height=38,Enabled=false };
        var older=new Button { Text="گزارش‌های قدیمی‌تر",Width=160,Height=38,Enabled=false };
        int reportOffset=0;int? nextOffset=null;var pageHistory=new Stack<int>();
        var output=new RichTextBox { Dock=DockStyle.Fill,ReadOnly=true,DetectUrls=true,Font=new Font("Tahoma",11) };
        output.LinkClicked+=(_,e)=> { if(Uri.TryCreate(e.LinkText,UriKind.Absolute,out var u) && u.Scheme=="https" && u.IsDefaultPort && u.UserInfo.Length==0)System.Diagnostics.Process.Start(new System.Diagnostics.ProcessStartInfo(u.AbsoluteUri) { UseShellExecute=true }); };
        string Route()=>topic.SelectedIndex==1?"/v1/research/iran":"/v1/research/calendar";
        void Render()=>output.Text=current is null?"گزارش در دسترس نیست.":RenderText(current,topic.SelectedIndex==1);
        async Task Load() { if(loading || IsDisposed)return;loading=true;newer.Enabled=older.Enabled=false;try { var data=await call("GET",Route()+"?report_offset="+reportOffset,null);if(IsDisposed)return;current=data;nextOffset=data["report_page"]?["next_offset"]?.GetValue<int>();filling=true;reports.Clear();archives.Items.Clear();if(data["reports"] is JsonArray rows)foreach(var row in rows.OfType<JsonObject>()) { reports.Add(row);archives.Items.Add("گزارش — "+Stamp(row["generated_ms"])); }if(archives.Items.Count>0) { int active=reports.FindIndex(row=>JsonNode.DeepEquals(row,data["last_report"]));archives.SelectedIndex=active>=0?active:0;if(reportOffset>0)current["last_report"]=reports[archives.SelectedIndex].DeepClone(); }filling=false;Render(); }catch { if(!IsDisposed)output.Text="اتصال برنامه برقرار نیست؛ گزارش و اثر پژوهش تازه تأیید نشد. هیچ سنجش یا سفارشی اجرا نشد."; }finally { loading=false;if(!IsDisposed) { newer.Enabled=pageHistory.Count>0;older.Enabled=nextOffset is not null; } } }
        archives.SelectedIndexChanged+=(_,_)=> { if(!filling && current is not null && archives.SelectedIndex>=0 && archives.SelectedIndex<reports.Count) { current["last_report"]=reports[archives.SelectedIndex].DeepClone();Render(); } };
        older.Click+=async (_,_)=> { if(nextOffset is int offset) { pageHistory.Push(reportOffset);reportOffset=offset;await Load(); } };
        newer.Click+=async (_,_)=> { if(pageHistory.TryPop(out int offset)) { reportOffset=offset;await Load(); } };
        topic.SelectedIndexChanged+=async (_,_)=> { consent.Checked=false;reportOffset=0;pageHistory.Clear();await Load(); };
        reload.Click+=async (_,_)=> { reportOffset=0;pageHistory.Clear();await Load(); };
        local.Click+=async (_,_)=> { local.Enabled=synthesize.Enabled=reload.Enabled=topic.Enabled=false;output.Text="در حال تحلیل محلی داده‌های دریافت‌شده…";
            try { await call("POST",Route()+"/local",new JsonObject());reportOffset=0;pageHistory.Clear();if(!IsDisposed)await Load(); }
            catch { if(!IsDisposed)output.Text="گزارش محلی ثبت نشد؛ داده یا اتصال برنامه را بررسی کن. داده‌ای به سرویس بیرونی ارسال نشد."; }
            finally { if(!IsDisposed) { local.Enabled=synthesize.Enabled=!reviewOnly;reload.Enabled=topic.Enabled=true; } }
        };
        synthesize.Click+=async (_,_)=> { if(!consent.Checked) { output.Text="برای سنجش آنلاین، رضایت ارسال گزیدهٔ منابع عمومی لازم است.";return; }synthesize.Enabled=reload.Enabled=topic.Enabled=false;output.Text="در حال سنجش شواهد عمومی…";
            try { await call("POST",Route()+(topic.SelectedIndex==1?"/synthesis":""),new JsonObject { ["consent"]=true });reportOffset=0;pageHistory.Clear();if(!IsDisposed)await Load(); }
            catch { if(!IsDisposed)output.Text="گزارش تازه تولید یا تأیید نشد. گزارش قبلی را با دکمه نمایش وضعیت بررسی کن. سفارش صادر نشد."; }
            finally { if(!IsDisposed) { synthesize.Enabled=!reviewOnly;reload.Enabled=topic.Enabled=true; } }
        };
        buttons.Controls.AddRange([local,synthesize,reload,newer,older]);Controls.Add(output);Controls.Add(archives);Controls.Add(buttons);Controls.Add(consent);Controls.Add(topic);Controls.Add(intro);
        var refreshTimer=new System.Windows.Forms.Timer { Interval=30000 };
        refreshTimer.Tick+=async (_,_)=> { if(Visible && reportOffset==0 && reload.Enabled)await Load(); };
        Shown+=async (_,_)=> { refreshTimer.Start();await Load(); };
        FormClosed+=(_,_)=>refreshTimer.Dispose();
    }
    private static string Stamp(JsonNode? value)=>long.TryParse(value?.ToString(),out var ms)?DateTimeOffset.FromUnixTimeMilliseconds(ms).ToLocalTime().ToString("yyyy/MM/dd HH:mm:ss"):"نامعلوم";
    internal static string DecisionReason(string reason)=>reason switch {
        "CALENDAR_CONFIRMS_CANDIDATE"=>"پژوهش نامزد را تأیید کرد؛ اجازهٔ نهایی با محافظ‌های مستقل است.",
        "CALENDAR_OPPOSES_CANDIDATE"=>"پژوهش با جهت نامزد مخالف است؛ ورود رد شد.",
        "CALENDAR_HORIZON_CONFLICT"=>"سناریوهای کوتاه‌مدت و بلندمدت تعارض دارند؛ ورود رد شد.",
        "CALENDAR_REPORT_STALE"=>"گزارش تازه یا زمان معتبر در دسترس نیست.",
        "CALENDAR_SOURCES_INSUFFICIENT"=>"حداقل دو منبع تازه و قابل ارجاع کافی نیست.",
        "CALENDAR_VALIDATION_REQUIRED"=>"ارزیابی مستقل کافی برای استفادهٔ پژوهش در سفارش وجود ندارد.",
        "CALENDAR_SIGNAL_MISSING"=>"گزارش فقط متن دارد و نتیجهٔ ساختاریافته ندارد.",
        "CALENDAR_REPORT_MISSING"=>"گزارش پژوهش هنوز ثبت نشده است.",
        "CALENDAR_UNCERTAINTY_HIGH"=>"عدم قطعیت پژوهش برای معامله کافی کاهش نیافته است.",
        "CALENDAR_NO_PRICE_CANDIDATE"=>"نامزد قیمت برای تأیید وجود ندارد.",
        _=>"پژوهش معتبر برای تصمیم هنوز تأیید نشده است."
    };
    internal static string RenderText(JsonObject state,bool iran) {
        string text=iran?"پژوهش آماری ایران؛ مستقل از معامله\n":"گزارش اقتصادی مستقل از معامله\n";
        if(state["independent_assurance"] is JsonObject assurance) {
            text+="گزارش‌های خودکار و نگهبان منابع\n";
            if(assurance["reports"] is JsonArray automatic)foreach(var item in automatic.OfType<JsonObject>()) {
                text+="آخرین ارزیابی: "+Stamp(item["observed_ms"])+"\n";
                if(item["continuous_activity"] is JsonObject activity && activity["source_guardians"] is JsonArray guardians) {
                    text+="چرخه گردآوری: "+Stamp(activity["observed_ms"])+"؛ وابسته به روشن بودن ویندوز و اینترنت\n";
                    foreach(var g in guardians.OfType<JsonObject>().Where(g=>g["scope"]?.ToString()==(iran?"iran":"calendar")).Take(80))
                        text+=g["id"]+" — "+g["status"]+"؛ علت: "+g["reason"]+"؛ خطا: "+(g["error_type"]?.ToString() ?? "ندارد")+"\nآخرین تلاش: "+Stamp(g["last_attempt_ms"])+"؛ موفق: "+Stamp(g["last_success_ms"])+"؛ تلاش بعد: "+Stamp(g["next_attempt_ms"])+"\n";
                }
            }
            if(assurance["economic_perspectives"] is JsonArray views)foreach(var v in views.OfType<JsonObject>())
                text+=v["name"]+": "+v["review_status"]+"\n";
        }
        if(state["observation_only"]?.GetValue<bool>()==true)text+="این اجرا برای بررسی و پژوهش است؛ ارسال و بستن سفارش مسدود است.\n";
        if(!iran) {
            var scheduled=state["scheduled_calendar"];
            if(scheduled?["source"]?.ToString()=="MT5-MetaQuotes-calendar" && scheduled["current"]?.GetValue<bool>()==true) {
                text+="تقویم داخلی متاتریدر — دریافت: "+Stamp(scheduled["received_ms"])+"\n";
                text+=scheduled["clear"]?.GetValue<bool>()==true?"در پنجرهٔ پوشش، رویداد برنامه‌ریزی‌شدهٔ پراثر USD مانع ورود نیست؛ این مجوز معامله یا پوشش خبر ناگهانی نیست.\n":"رویداد پراثر نزدیک است؛ ورود خبری رد شده است.\n";
                if(scheduled["events"] is JsonArray releases)foreach(var release in releases)text+="رویداد پراثر USD — "+release?["title"]+"؛ "+Stamp(release?["time_ms"])+"\n";
            } else text+="پوشش تازهٔ تقویم داخلی متاتریدر تأیید نشده است.\n";
            text+="تقویم و سنتیمنت هیچ اختیار تأیید، رد یا ساخت سفارش ندارند.\n";
            var evaluation=state["forecast_evaluation"];text+="پیش‌بینی‌های مستقلِ ارزیابی‌شده: "+(evaluation?["independent_sample_count"]?.ToString() ?? "۰")+"؛ در انتظار نتیجه: "+(evaluation?["pending_count"]?.ToString() ?? "۰")+"\n";
            text+="هدف‌های ازدست‌رفتهٔ دو ساعته: "+(evaluation?["missed_count"]?.ToString() ?? "۰")+"\n";
            var longEvaluation=state["long_forecast_evaluation"];text+="افق هفت‌روزه — نمونهٔ مستقل: "+(longEvaluation?["independent_sample_count"]?.ToString() ?? "۰")+"؛ منتظر نتیجه: "+(longEvaluation?["pending_count"]?.ToString() ?? "۰")+"؛ مستقل از افق ورود دو ساعته.\n";
            if(double.TryParse(evaluation?["accuracy"]?.ToString(),System.Globalization.NumberStyles.Float,System.Globalization.CultureInfo.InvariantCulture,out var accuracy))text+="نسبت موفقیت مشاهده‌شده: "+(accuracy*100).ToString("F1")+"٪؛ تضمین آینده نیست.\n";
            text+=evaluation?["deployment_eligible"]?.GetValue<bool>()==true?"ارزیابی پژوهش واجد شرایط است؛ اجازهٔ مالک و محافظ‌ها همچنان لازم‌اند.\n":"ارزیابی مستقل کافی برای استفاده در سفارش هنوز تأیید نشده است.\n";
        } else {
            text+="به‌روزرسانی برنامه‌ریزی‌شده: هر ساعت؛ زمان دریافت با دورهٔ آمار فرق دارد.\n";
            var statistics=state["statistics"];text+="زمان شروع دریافت: "+Stamp(statistics?["observed_ms"])+"\n";
            if(statistics?["changes"] is JsonNode changes)text+="دادهٔ تازه: "+changes["new"]+"؛ اصلاحی: "+changes["revisions"]+"؛ مبنای اولیه: "+changes["baseline"]+"\n";
            if(statistics?["series"] is JsonArray series)foreach(var row in series) {
                text+="\n"+IranSourceTitle(row?["id"]?.ToString())+" — "+(row?["status"]?.ToString()=="available"?(row?["cached"]?.GetValue<bool>()==true?"از حافظه با زمان اصلی؛ دریافت تازه ناموفق":"دریافت واقعی انجام شد"):"ناموجود؛ مقدار صفر نیست")+"\n"+row?["source_url"]+"\n";
                if(row?["observations"] is JsonArray observations)foreach(var item in observations.Take(12))text+=item?["title"]+"؛ دوره: "+item?["period"]+"؛ مقدار: "+item?["value"]+" "+item?["unit"]+"\nکیفیت: "+QualityText(item?["quality"]?.ToString())+"؛ زمان دریافت: "+Stamp(item?["received_ms"])+"؛ زمان انتشار: "+Stamp(item?["published_ms"])+"\n";
            }
            text+="\nپوشش موضوع‌ها و محدودیت‌ها:\n";
            if(statistics?["definitions"] is JsonArray definitions)foreach(var item in definitions)text+=item?["title"]+" — "+CoverageText(item?["status"]?.ToString())+"\n";
            text+="سری سالانه، آمار ماه جاری نیست؛ نرخ رسمی ارز با نرخ آزاد فرق دارد.\n";
        }
        var report=state["last_report"] as JsonObject;
        if(report?["provider"]?.ToString()=="local-public-evidence")text+="\nروش این گزارش محلی است؛ هیچ داده‌ای به مدل بیرونی ارسال نشده است.\n";
        text+=report is null?"\nهنوز گزارش ترکیبی ثبت نشده است.\n":"\nگزارش ثبت‌شده — "+Stamp(report["generated_ms"])+"\n"+report["answer"]+"\n";
        // Same report payload, no new API or mutation. Avoid rendering twice when
        // the existing answer already includes the shared Persian explanation.
        var intelligence=report?["calendar_intelligence"];
        if(intelligence?["rendered_fa"] is JsonValue explanation &&
           !(report?["answer"]?.ToString() ?? "").Contains(explanation.ToString()))
            text+="\n★ تقویم — بازنگری شواهد\n"+explanation+"\n";
        if(report?["foresight_framework"] is JsonNode framework) {
            text+="\nچارچوب اجرایی سناریو و بازبینی:\n"+framework["summary_fa"]+"\nاین طبقه‌بندی برداشت مهندسی از منابع خوانده‌شده است؛ فرمول خرید و فروشِ منسوب به نویسنده نیست.\n";
            if(framework["drivers"] is JsonArray drivers)foreach(var d in drivers)text+="پیشران — "+d?["actor"]+": "+d?["value"]+" "+d?["unit"]+"؛ دوره "+d?["period"]+"؛ "+DriverState(d?["state"]?.ToString())+"\n";
            if(framework["domain_scan"] is JsonArray domains) {
                text+="پویش حوزه‌ها؛ وجود منبع به معنی کامل‌بودن پوشش نیست:\n";
                foreach(var d in domains)text+=d?["title"]+" — "+DomainStatus(d?["status"]?.ToString())+"\n";
            }
            if(framework["indicator_support"] is JsonNode support)foreach(string horizon in new[]{"short_term","long_term"}) {
                var counts=support[horizon];text+=(horizon=="short_term"?"شاخص‌های کوتاه‌مدت: ":"شاخص‌های بلندمدت: ")+"افزایشی "+counts?["rising"]+"، کاهشی "+counts?["falling"]+"، ثابت "+counts?["stable"]+"، نامعلوم "+counts?["unknown"]+"؛ این شمارش احتمال وقوع نیست.\n";
            }
            if(framework["exploration"]?["logic_assessments"] is JsonArray logics)foreach(var logic in logics) {
                string name=logic?["logic"]?.ToString() switch { "winners-losers"=>"برندگان و بازندگان", "challenge-response"=>"چالش و پاسخ", "evolution"=>"تکامل روند", "revolution"=>"تغییر ساختار", "cycles"=>"چرخه‌ها", _=>"منطق سناریو" };
                text+=name+" — "+(logic?["status"]?.ToString()=="assessed-observation-pattern"?"الگوی تغییر مشاهدات سنجیده شد؛ علیت نتیجه‌گیری نشده است.":"ورودی تأییدشده برای اجرای این منطق کافی نیست.")+"\n";
            }
            if(framework["cross_impact"] is JsonNode impact)text+="تحلیل اثرات متقابل — "+(impact["status"]?.ToString()=="computed"?"جمع اثرگذاری و وابستگی مستقیم محاسبه شد؛ امتیازها احتمال یا علیت اثبات‌شده نیستند.":"ماتریس کامل کارشناسیِ قابل ارجاع موجود نیست؛ امتیاز یا اثر بازار ساخته نشده است.")+"\n";
            if(framework["hormuz_exploration"] is JsonNode grid) {
                text+="چهار آیندهٔ شرطی هرمز؛ ارزیابی مستقیم درگیری و تاب‌آوری انرژی برای انتخاب لازم است:\n";
                if(grid["scenarios"] is JsonArray alternatives)foreach(var row in alternatives)text+=row?["title"]+" — "+(row?["active_under_supplied_assessments"]?.GetValue<bool>()==true?"سازگار با ارزیابی ورودی؛ اعتبار مستقل تأیید نشده":"سناریوی بدیل؛ وقوع تأیید نشده")+"\n";
                text+="احتمال و آستانهٔ هشدار اعتبارسنجی‌شده موجود نیست؛ جهت طلا نتیجه‌گیری نمی‌شود.\n";
            }
            if(framework["scenarios"] is JsonArray scenarios)foreach(var scenario in scenarios)text+=(scenario?["active"]?.GetValue<bool>()==true?"✓ فعال: ":"بدیل: ")+(scenario?["horizon"]?.ToString()=="short_term"?"کوتاه‌مدت — ":"بلندمدت — ")+scenario?["title"]+"\nشرط: "+scenario?["condition"]+"\n";
            if(framework["revision_conditions"] is JsonArray conditions)text+="شرط‌های بازبینی: "+string.Join("؛ ",conditions.Select(x=>x?.ToString()))+"\n";
            if(framework["revision_triggers"] is JsonArray changes)text+="پیشران‌های تغییرکرده در مقایسه با گزارش قبلی: "+changes.Count+"\n";
        }
        if(state["historical_evaluation"] is JsonNode history)text+="\nارزیابی تاریخی، مستقل از پیش‌بینی‌های آینده:\n"+(history["summary_fa"]?.ToString() ?? "نتیجهٔ تاریخی در گزارش مستقل ثبت شده است؛ مجوز سفارش نیست.")+"\n";
        var evidence=report?["evidence"] ?? state["evidence"];
        if(!iran) {
            text+="\nمنابع همان گزارش:\n";
            if(evidence?["public_sources"] is JsonArray sources)foreach(var row in sources)text+=row?["id"]+" — "+(row?["status"]?.ToString()=="available"?"در زمان تهیه دریافت شده":"ناموجود یا قدیمی")+"\n"+row?["source_url"]+"\n";
            var coverage=evidence?["foresight_review"];
            text+="\nپوشش آثار مطهرنیا — متن کامل مقاله‌ها و گفت‌وگوهای مکتوب بررسی‌شده: "+(coverage?["complete_article_bodies_reviewed"]?.ToString() ?? "نامعلوم")+"؛ معرفی کتاب‌ها: "+(coverage?["book_catalogs_reviewed"]?.ToString() ?? "نامعلوم")+". متن کامل کتاب‌های فاقد دسترسی مطالعه نشده است. برداشت مهندسی سناریوها از روش کامل نویسنده جداست.\n";
            if(evidence?["references"] is JsonArray references)foreach(var row in references)text+=row?["title"]+"\n"+row?["note"]+"\n"+row?["url"]+"\n\n";
        }
        return text;
    }
    private static string IranSourceTitle(string? id)=>id switch {
        "inflation_annual"=>"تورم سالانه — بانک جهانی", "growth_annual"=>"رشد اقتصادی سالانه — بانک جهانی", "unemployment_annual"=>"بیکاری سالانه — بانک جهانی",
        "broad_money_annual"=>"پول گستردهٔ سالانه — تاریخی", "official_fx_annual"=>"میانگین سالانهٔ نرخ رسمی ارز",
        "cbi_inflation"=>"نرخ منتهی به ماه — بانک مرکزی؛ تعریف جدا", "sci_cpi"=>"مرکز آمار — شاخص و سه تعریف تورم",
        "tsetmc"=>"بورس — شاخص‌ها و گردش بازار", "cbi_money"=>"بانک مرکزی — نقدینگی و پایه پولی", "sci_labor_quarterly"=>"مرکز آمار — بازار کار فصلی کل کشور", "sci_household_annual"=>"مرکز آمار — درآمد و هزینهٔ اسمی خانوار و ضریب جینی", "lmo_fight_referrals"=>"پزشکی قانونی — شمار ثبت‌شدهٔ مراجعان نزاع؛ شاخص امنیت نیست", _=>"منبع آماری" };
    private static string QualityText(string? quality)=>quality switch {
        "historical_annual"=>"سری سالانه؛ آمار ماه جاری نیست", "historical_annual_lagged"=>"سری تاریخی با تأخیر زیاد",
        "official_monthly_publication_time_unverified"=>"دادهٔ رسمی ماهانه؛ زمان انتشار تأیید نشده", "official_quarterly_publication_time_unverified"=>"دادهٔ رسمی فصلی؛ آمار ماه جاری نیست و زمان انتشار تأیید نشده", "official_period_stock_lagged"=>"ماندهٔ رسمیِ دورهٔ منتشرشده؛ آمار ماه جاری نیست",
        "official_annual_nominal_publication_time_unverified"=>"آمار سالانه با قیمت جاری؛ درآمد واقعی یا آمار ماه جاری نیست", "official_annual_publication_time_unverified"=>"آمار رسمی سالانه؛ زمان انتشار تأیید نشده", "official_cumulative_referrals_publication_time_unverified"=>"مراجعهٔ ثبت‌شده در دورهٔ تجمعی؛ نه کل وقوع نزاع، نرخ جرم یا شاخص امنیت", "dated_market_snapshot"=>"تصویر بازار با زمان منبع؛ محدودیت واحد ارزش معامله را بررسی کن", _=>"دوره و تعریف منبع را بررسی کن" };
    private static string CoverageText(string? status)=>status switch { "available"=>"دادهٔ رسمی دریافت شده؛ دوره را بررسی کن", "available_alternative_definition"=>"داده با تعریف متفاوت؛ پوشش کامل نیست", "available_with_unit_limitation"=>"داده دریافت شده؛ محدودیت واحد ارزش معاملات باقی است", "available_lagged_period"=>"دادهٔ رسمیِ دورهٔ منتشرشده؛ آمار ماه جاری نیست", _=>"داده متصل نیست" };
    private static string DomainStatus(string? status)=>status switch { "comparable-observation"=>"مشاهدهٔ قابل مقایسه موجود است", "source-only"=>"منبع موجود است؛ مشاهدهٔ قابل مقایسه کافی نیست", _=>"دادهٔ مستقیم کافی نداریم" };
    private static string DriverState(string? state)=>state switch { "rising"=>"افزایش نسبت به دورهٔ قابل مقایسه", "falling"=>"کاهش نسبت به دورهٔ قابل مقایسه", "stable"=>"بدون تغییر", _=>"شاهد مقایسه‌پذیر کافی نیست" };
}
