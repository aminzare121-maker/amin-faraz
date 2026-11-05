using Microsoft.Web.WebView2.Core;
using Microsoft.Web.WebView2.WinForms;

namespace Amin.Owner;

internal sealed class CalendarPage : Form
{
    private const string Calendar="https://www.tradays.com/en/economic-calendar/widget?mode=2&utm_source=core.eplanetbrokers.com";
    private readonly WebView2 web=new() { Dock=DockStyle.Fill };
    private readonly Label status=new() { Dock=DockStyle.Top,Height=90,Padding=new Padding(10),Text="تقویم Tradays، همان ارائه‌دهندهٔ تقویم کابین ای‌پلنت. در حال دریافت…\nنمایش برای مشاهده است؛ محافظ خبر ربات با بازشدن این صفحه تأیید نمی‌شود." };
    internal CalendarPage(Action? openAminCalendar=null) {
        Text="تقویم اقتصادی";BackColor=Color.White;ForeColor=Color.FromArgb(15,38,83);RightToLeft=RightToLeft.Yes;Size=new Size(960,750);Controls.Add(web);Controls.Add(status);
        if(openAminCalendar is not null) { var amin=new Button { Text="تقویم اقتصادی امین — نتیجهٔ پژوهش‌ها",Dock=DockStyle.Top,Height=45,BackColor=Color.FromArgb(15,38,83),ForeColor=Color.White,UseVisualStyleBackColor=false };amin.Click+=(_,_)=>openAminCalendar();Controls.Add(amin); }
        Shown+=async (_,_)=>await Initialize();FormClosed+=(_,_)=>web.Dispose();
    }
    private static bool Trusted(string address)=>Uri.TryCreate(address,UriKind.Absolute,out var u) && u.Scheme=="https" && u.Host=="www.tradays.com" && u.IsDefaultPort && u.UserInfo.Length==0;
    private async Task Initialize() {
        try {
            var env=await CoreWebView2Environment.CreateAsync(null,Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData),"AminOwner","CalendarWebView"),new CoreWebView2EnvironmentOptions("--no-proxy-server"));
            if(IsDisposed)return;await web.EnsureCoreWebView2Async(env);if(IsDisposed)return;
            web.CoreWebView2.IsMuted=true;
            web.CoreWebView2.Settings.IsWebMessageEnabled=false;web.CoreWebView2.Settings.AreHostObjectsAllowed=false;web.CoreWebView2.Settings.AreDevToolsEnabled=false;
            web.CoreWebView2.Profile.IsPasswordAutosaveEnabled=false;web.CoreWebView2.Profile.IsGeneralAutofillEnabled=false;
            web.CoreWebView2.NewWindowRequested+=(_,e)=>e.Handled=true;web.CoreWebView2.DownloadStarting+=(_,e)=>e.Cancel=true;
            web.CoreWebView2.NavigationStarting+=(_,e)=> { if(!Trusted(e.Uri))e.Cancel=true; };
            web.CoreWebView2.NavigationCompleted+=(_,e)=>status.Text=(e.IsSuccess && e.HttpStatusCode>=200 && e.HttpStatusCode<400?"تقویم دریافت شد؛ ساعت رویدادها و منطقهٔ زمانی را در خود تقویم بررسی کن.":"تقویم دریافت نشد؛ اتصال موفق اعلام نمی‌شود.")+"\nمنبع: Tradays، ارائه‌دهندهٔ تقویم کابین ای‌پلنت. مشاهدهٔ این صفحه، تأیید خبر برای سفارش نیست.";
            web.CoreWebView2.Navigate(Calendar);
        } catch { if(!IsDisposed)status.Text="مرورگر تقویم راه‌اندازی نشد. محافظ خبر همچنان مستقل و بسته می‌ماند."; }
    }
}
