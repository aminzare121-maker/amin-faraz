# Windows 11: launch only a free local model on this PC.
# No purchases, no API cloud credits, no external service hosting.
# Requires Python, Ollama and the model to be installed beforehand.
param(
    [string]$Model = "qwen2.5:7b-instruct",
    [int]$Port = 8765
)
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
if (!(Test-Path (Join-Path $root "amin_support.py"))) {
    throw "File amin_support.py not found beside this launcher."
}
if (!(Get-Command python -ErrorAction SilentlyContinue)) {
    throw "Python not available. No automatic installation attempted."
}
if (!(Get-Command ollama -ErrorAction SilentlyContinue)) {
    throw "Ollama must already be installed. No automatic download attempted."
}
if ($Port -lt 1024 -or $Port -gt 65535) {
    throw "Select a local port 1024-65535."
}
$available = & ollama list 2>&1
if ($LASTEXITCODE -ne 0 -or ($available -notmatch [regex]::Escape($Model))) {
    throw "Local model '$Model' unavailable. Nothing purchased or downloaded."
}
$env:AMIN_ZERO_PAYMENT_MODE = "on"
$env:AMIN_MODEL_BASE_URL = "http://127.0.0.1:11434/v1"
$env:AMIN_MODEL_NAME = $Model
$env:AMIN_MODEL_API_KEY = ""
$env:AMIN_MODEL_REMOTE_CONSENT = ""
$env:AMIN_MODEL_INTERNAL_CONSENT = ""
Write-Host "Zero-payment local-only model mode active."
Write-Host "Support UI: http://127.0.0.1:$Port"
Set-Location $root
& python amin_support.py serve --host 127.0.0.1 --port $Port
