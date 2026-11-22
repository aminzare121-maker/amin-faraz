# Direct SIWC ChatGPT plan usage for the laptop owner: no Codex, Work or paid API key.
param(
    [ValidateSet("login", "status", "models", "ask", "logout")]
    [string]$Command = "status"
)
$ErrorActionPreference = "Stop"
$path = Join-Path (Split-Path $PSScriptRoot -Parent) "chatgpt_plan_direct.py"
if (-not (Test-Path $path)) { throw "chatgpt_plan_direct.py missing" }
if (-not (Get-Command python -ErrorAction SilentlyContinue)) {
    throw "Python 3.11 or newer is needed."
}
switch ($Command) {
  "login" {
     Write-Host "Your browser will open the official ChatGPT authorization page."
     Write-Host "No OpenAI API key is required and this script does not buy credits."
     & python $path login
  }
  "status" { & python $path status }
  "models" { & python $path models }
  "ask" {
     Write-Host "Enter a question on the next line. No content will go to GitHub."
     $message = Read-Host "Question"
     if (-not [string]::IsNullOrWhiteSpace($message)) {
         $message | & python $path ask
     }
  }
  "logout" { & python $path logout }
}
