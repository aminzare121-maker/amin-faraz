# Secure Windows CLI for GitHub private relay. All existing four operations remain.
param([string]$Repo = "")

$ErrorActionPreference = "Stop"
$env:PYTHONIOENCODING = "utf-8"
$client = Join-Path (Split-Path $PSScriptRoot -Parent) "direct_github_relay.py"
if (-not (Test-Path $client)) { Write-Host "direct_github_relay.py پیدا نشد."; exit 2 }
if (-not (Get-Command python -ErrorAction SilentlyContinue)) {
    Write-Host "Python روی سیستم موجود نیست."; exit 2
}
if ([string]::IsNullOrWhiteSpace($Repo)) {
    $Repo = Read-Host "نام مخزن خصوصی (owner/repo)"
}
Write-Host "توکن فقط در این نشست نگهداری می‌شود."
$secure = Read-Host "توکن GitHub با اجازه Issues" -AsSecureString
$bstr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secure)
try { $env:AMIN_PRIVATE_GITHUB_TOKEN = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($bstr) }
finally { [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($bstr) }
try {
    & python $client --repo $Repo verify
    if ($LASTEXITCODE -ne 0) {
        Write-Host "اتصال به مخزن خصوصی موفق نبود."; exit 2
    }
    while ($true) {
        Write-Host ""
        Write-Host "1-ارسال خصوصی | 2-فهرست | 3-پاسخ | 4-تأیید یادگیری | 0-خروج"
        $choice = Read-Host "انتخاب"
        switch ($choice) {
            "1" {
                $project = Read-Host "شناسه نرم‌افزار"
                $message = Read-Host "متن درخواست"
                if (-not [string]::IsNullOrWhiteSpace($message)) {
                    $consent = Read-Host "ثبت متن در مخزن خصوصی را تأیید می‌کنی؟ (yes/no)"
                    if ($consent -eq "yes") {
                        & python $client --repo $Repo submit --project $project --message $message
                    }
                }
            }
            "2" { & python $client --repo $Repo list }
            "3" {
                $number = Read-Host "شماره Issue"
                $rid = Read-Host "شناسه 32 رقمی درخواست"
                if ($number -match '^[1-9][0-9]*$') {
                    & python $client --repo $Repo status --issue $number --id $rid
                } else { Write-Host "شماره Issue معتبر نیست." }
            }
            "4" {
                $number = Read-Host "شماره Issue"
                $rid = Read-Host "شناسه 32 رقمی درخواست"
                $project = Read-Host "شناسه نرم‌افزار"
                if ($number -match '^[1-9][0-9]*$') {
                    $yes = Read-Host "پاسخ بررسی و تأیید شده است؟ (yes/no)"
                    if ($yes -eq "yes") {
                        & python $client --repo $Repo approve --issue $number --id $rid --project $project
                    }
                } else { Write-Host "شماره Issue معتبر نیست." }
            }
            "0" { break }
            default { Write-Host "گزینه نامعتبر است." }
        }
        if ($choice -eq "0") { break }
    }
}
finally {
    Remove-Item Env:\AMIN_PRIVATE_GITHUB_TOKEN -ErrorAction SilentlyContinue
    Remove-Item Env:\PYTHONIOENCODING -ErrorAction SilentlyContinue
    Write-Host "توکن خصوصی نشست از متغیر محیطی پاک شد."
}
