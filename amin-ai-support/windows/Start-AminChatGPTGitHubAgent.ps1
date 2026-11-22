# Owner-hosted ChatGPT-plan GitHub agent. Never uses Codex, Work or API credits.
# Requires an existing authorized ChatGPT SIWC login and a repo-scoped GitHub token.
param(
    [string]$Repo = "",
    [switch]$ReadOnly
)
$ErrorActionPreference = "Stop"
$root = Split-Path $PSScriptRoot -Parent
$agent = Join-Path $root "chatgpt_git_agent.py"
if (-not (Test-Path $agent)) { throw "chatgpt_git_agent.py missing" }
if (-not (Get-Command python -ErrorAction SilentlyContinue)) {
    throw "Python 3.11+ is needed on this Windows PC"
}
if ([string]::IsNullOrWhiteSpace($Repo)) {
    $Repo = Read-Host "نام مخزن مجاز GitHub (owner/repository)"
}
if ($Repo -notmatch '^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$') {
    throw "مخزن معتبر نیست"
}
Write-Host "این برنامه با ورود ChatGPT و سهمیه مجاز همان حساب کار می‌کند."
Write-Host "Codex یا Work فراخوانی نمی‌شود؛ خرید API ایجاد نمی‌کند."
$credential = Read-Host "توکن محدود GitHub همان مخزن" -AsSecureString
$bstr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($credential)
try {
    $env:AMIN_AGENT_GITHUB_TOKEN = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($bstr)
} finally {
    [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($bstr)
}
try {
    $question = Read-Host "چه تغییری می‌خواهی؟"
    if ([string]::IsNullOrWhiteSpace($question)) { throw "درخواست نمی‌تواند خالی باشد" }
    $writeApproval = $false
    if (-not $ReadOnly.IsPresent) {
        $approval = Read-Host "اجازهٔ اصلاح کد در شاخهٔ جدا و ساخت PR پیش‌نویس؟ (yes/no)"
        $writeApproval = $approval -eq "yes"
    }
    $publicApproval = $false
    if ($writeApproval) {
        $publicApproval = (Read-Host "اگر مخزن عمومی است، اجازهٔ انتشار کد در همان مخزن؟ (yes/no)") -eq "yes"
    }
    $arguments = @($agent, "--repo", $Repo, "--question", $question)
    if ($writeApproval) { $arguments += "--approve-write" }
    if ($publicApproval) { $arguments += "--allow-public" }
    & python @arguments
    if ($LASTEXITCODE -ne 0) {
        Write-Host "اجرای عامل کامل یا موفق تأیید نشد. خطای بالا را بررسی کن."
        exit $LASTEXITCODE
    }
} finally {
    Remove-Item Env:\AMIN_AGENT_GITHUB_TOKEN -ErrorAction SilentlyContinue
    Write-Host "کلید GitHub از محیط این نشست پاک شد."
}
