# پل مستقیم مخزن خصوصی هوش امین — Windows PowerShell
# This script does not upload a secret into GitHub. No external paid model.
param([string]$Repo = "aminzare121-maker/amin-mt5-review")

$ErrorActionPreference = "Stop"
$env:PYTHONIOENCODING = "utf-8"
$client = Join-Path (Split-Path $PSScriptRoot -Parent) "direct_github_relay.py"
if (-not (Test-Path $client)) {
    Write-Host "فایل direct_github_relay.py پیدا نشد."
    exit 2
}
if (-not (Get-Command python -ErrorAction SilentlyContinue)) {
    Write-Host "Python روی این ویندوز در دسترس نیست؛ این رابط نمی‌تواند اجرا شود."
    exit 2
}
Write-Host "هوش امین - اتصال به مخزن خصوصی GitHub"
Write-Host "مخزن مقصد: $Repo"
Write-Host "توکن فقط برای همین جلسه استفاده می‌شود. مخزن باید خصوصی باشد."
$secure = Read-Host "توکن GitHub با مجوز محدود Issues" -AsSecureString
$bstr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secure)
try {
    $env:AMIN_PRIVATE_GITHUB_TOKEN = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($bstr)
}
finally {
    [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($bstr)
}
try {
    & python $client --repo $Repo verify
    if ($LASTEXITCODE -ne 0) {
        Write-Host "اتصال امن تأیید نشد؛ هیچ درخواستی ارسال نمی‌شود."
        exit 2
    }
    while ($true) {
        Write-Host ""
        Write-Host "1 - ارسال درخواست خصوصی"
        Write-Host "2 - فهرست درخواست‌ها"
        Write-Host "3 - دریافت پاسخ"
        Write-Host "4 - تأیید پاسخ بررسی‌شده برای یادگیری"
        Write-Host "0 - خروج و حذف کلید این جلسه"
        $choice = Read-Host "انتخاب"
        switch ($choice) {
            "1" {
                $project = Read-Host "شناسه برنامه (مثلاً support)"
                $message = Read-Host "متن درخواست"
                if (-not [string]::IsNullOrWhiteSpace($message)) {
                    $consent = Read-Host "متن در Issue خصوصی GitHub ثبت شود؟ (yes/no)"
                    if ($consent -eq "yes") {
                        & python $client --repo $Repo submit --project $project --message $message
                    }
                }
            }
            "2" { & python $client --repo $Repo list }
            "3" {
                $number = Read-Host "شماره Issue"
                $rid = Read-Host "شناسه ۳۲ رقمی درخواست"
                if ($number -match '^[1-9][0-9]*$') {
                    & python $client --repo $Repo status --issue $number --id $rid
                } else { Write-Host "شماره Issue نامعتبر است." }
            }
            "4" {
                $number = Read-Host "شماره Issue"
                $rid = Read-Host "شناسه ۳۲ رقمی درخواست"
                $project = Read-Host "شناسه برنامه"
                if ($number -match '^[1-9][0-9]*
            default { Write-Host "انتخاب معتبر نیست." }
        }
        if ($choice -eq "0") { break }
    }
}
finally {
    Remove-Item Env:\AMIN_PRIVATE_GITHUB_TOKEN -ErrorAction SilentlyContinue
    Remove-Item Env:\PYTHONIOENCODING -ErrorAction SilentlyContinue
    Write-Host "کلید نشست از محیط برنامه پاک شد."
}
) {
                    $decision = Read-Host "پاسخ را واقعاً بررسی و تأیید می‌کنی؟ (yes/no)"
                    if ($decision -eq "yes") {
                        & python $client --repo $Repo approve --issue $number --id $rid --project $project
                    }
                } else { Write-Host "شماره Issue نامعتبر است." }
            }
            "0" { break }
            default { Write-Host "انتخاب معتبر نیست." }
        }
        if ($choice -eq "0") { break }
    }
}
finally {
    Remove-Item Env:\AMIN_PRIVATE_GITHUB_TOKEN -ErrorAction SilentlyContinue
    Remove-Item Env:\PYTHONIOENCODING -ErrorAction SilentlyContinue
    Write-Host "کلید نشست از محیط برنامه پاک شد."
}
