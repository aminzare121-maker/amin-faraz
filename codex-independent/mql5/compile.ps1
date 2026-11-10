param([Parameter(Mandatory=$true)][string]$MetaEditor)
$ErrorActionPreference = 'Stop'
$source = Join-Path $PSScriptRoot 'ArtinIndependentCapture.mq5'
$binary = Join-Path $PSScriptRoot 'ArtinIndependentCapture.ex5'
$reports = Join-Path (Split-Path $PSScriptRoot -Parent) 'reports'
$log = Join-Path $reports 'metaeditor-compile.log'
if (!(Test-Path -LiteralPath $MetaEditor -PathType Leaf)) { throw 'METAEDITOR_NOT_FOUND' }
New-Item -ItemType Directory -Path $reports -Force | Out-Null
$started = Get-Date
$arguments = @('/compile:"' + $source + '"', '/log:"' + $log + '"')
$compiler = Start-Process -FilePath $MetaEditor -ArgumentList $arguments -WindowStyle Hidden -PassThru
if (!$compiler.WaitForExit(60000)) { throw 'COMPILE_TIMEOUT_NO_SUCCESS_CLAIM' }
if (!(Test-Path -LiteralPath $binary) -or !(Test-Path -LiteralPath $log)) { throw 'REAL_COMPILE_OUTPUT_MISSING' }
$logText = Get-Content -LiteralPath $log -Raw
if ($logText -notmatch 'Result: 0 errors, 0 warnings,') { throw 'COMPILE_RESULT_NOT_CLEAN' }
if ((Get-Item -LiteralPath $binary).LastWriteTime -lt $started.AddSeconds(-2)) { throw 'STALE_EX5' }
$publishedLog = Join-Path $reports 'metaeditor-compile-sanitized.txt'
$logText.Replace((Split-Path $source -Parent), '[INDEPENDENT_MQL_SOURCE]') | Set-Content -LiteralPath $publishedLog -Encoding utf8
$result = [ordered]@{
  schema='codex_independent_actual_metaeditor_compile_v1'; compiled=$true; errors=0; warnings=0
  source_sha256=(Get-FileHash -LiteralPath $source -Algorithm SHA256).Hash.ToLower()
  ex5_sha256=(Get-FileHash -LiteralPath $binary -Algorithm SHA256).Hash.ToLower()
  original_log_sha256=(Get-FileHash -LiteralPath $log -Algorithm SHA256).Hash.ToLower()
  published_log_sha256=(Get-FileHash -LiteralPath $publishedLog -Algorithm SHA256).Hash.ToLower()
  compiler_file_version=(Get-Item -LiteralPath $MetaEditor).VersionInfo.FileVersion
  checked_utc=[DateTime]::UtcNow.ToString('o'); actual_mql_runtime_verified=$false
  orders_enabled=$false
}
$result | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $reports 'actual-compile.json') -Encoding utf8
$result | ConvertTo-Json -Compress
