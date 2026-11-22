# Amin live full-duplex Windows client, safe project-scoped token.
param([string]$Url = "ws://127.0.0.1:8766")
$ErrorActionPreference = "Stop"
$root = Split-Path $PSScriptRoot -Parent
$client = Join-Path $root "live_client.py"
if (-not (Test-Path $client)) { throw "live_client.py does not exist" }
if (-not (Get-Command python -ErrorAction SilentlyContinue)) {
    throw "Python is not available on this Windows computer"
}
$secret = Read-Host "کلید دسترسی اختصاصی نرم افزار" -AsSecureString
$bstr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secret)
try {
    $env:AMIN_SUPPORT_CLIENT_TOKEN = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($bstr)
} finally {
    [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($bstr)
}
try {
    $env:PYTHONIOENCODING = "utf-8"
    Write-Host "در حال راه اندازی کانال زنده با نشانی $Url"
    & python $client --url $Url
} finally {
    Remove-Item Env:\AMIN_SUPPORT_CLIENT_TOKEN -ErrorAction SilentlyContinue
    Remove-Item Env:\PYTHONIOENCODING -ErrorAction SilentlyContinue
    Write-Host "کلید از محیط این نشست پاک شد."
}
