# Artin V13: source-identical, read-only MQL5 compilation gate on Windows.
# Never attaches an EA to a chart or touches an MT5 account/order.
param([string]$MetaEditorPath = '')
$ErrorActionPreference = 'Stop'
$SourceName = 'ArtinV13_ShadowProbe_RecoveryV2_DemoOnly.mq5'
$ExpectedSourceSHA256 = '66f65c92275999e41835a1c414263cf7c5dd0ef4ea219dbef0e96b030bdcd361'
$BundlePath = Split-Path -Parent $MyInvocation.MyCommand.Path
$SourcePath = Join-Path $BundlePath $SourceName
$Root = Join-Path $env:LOCALAPPDATA 'ArtinV13\compile-check-v3'
$ReceiptPath = Join-Path $Root 'artin_v13_metaeditor_compile_receipt.json'
$LogPath = Join-Path $Root 'ArtinV13_ShadowProbe_RecoveryV2_DemoOnly.log'
$OutPath = Join-Path $Root 'ArtinV13_ShadowProbe_RecoveryV2_DemoOnly.ex5'
$CopiedSource = Join-Path $Root $SourceName
$Receipt = [ordered]@{
  schema = 'artin_mt5_metaeditor_compile_receipt_v3'
  phase = 'METAEDITOR_COMPILE_CHECK'
  status = 'NOT_RUN'
  generated_at = (Get-Date).ToString('o')
  source_sha256_expected = $ExpectedSourceSHA256
  source_sha256_verified = $false
  metaeditor_path = $null
  compiler_exit_code = $null
  log_path = $LogPath
  log_sha256 = $null
  ex5_path = $OutPath
  ex5_sha256 = $null
  log_reports_zero_errors = $false
  log_reports_errors = $null
  error = $null
  demo_runtime_tested = $false
  mt5_orders_sent = 0
  teacher_semantics_certified = $false
}
$Success = $false
try {
  New-Item -Path $Root -ItemType Directory -Force | Out-Null
  if (-not (Test-Path -LiteralPath $SourcePath -PathType Leaf)) { throw 'SOURCE_NOT_FOUND_IN_PACKAGE' }
  $ActualHash = (Get-FileHash -LiteralPath $SourcePath -Algorithm SHA256).Hash.ToLowerInvariant()
  if ($ActualHash -ne $ExpectedSourceSHA256) { throw 'SOURCE_SHA256_MISMATCH' }
  $Receipt.source_sha256_verified = $true

  # Locate a MetaEditor already installed by the owner. Never download or install one.
  $Candidates = New-Object 'System.Collections.Generic.List[string]'
  if ($MetaEditorPath) { $Candidates.Add($MetaEditorPath) }
  foreach ($Base in @($env:ProgramFiles, ${env:ProgramFiles(x86)})) {
    if (-not $Base -or -not (Test-Path -LiteralPath $Base)) { continue }
    foreach ($Folder in @('MetaTrader 5', 'MetaTrader5', 'Eplanet', 'EPlanet', 'Eplanet MetaTrader 5')) {
      foreach ($Exe in @('metaeditor64.exe', 'metaeditor.exe')) {
        $Candidates.Add((Join-Path (Join-Path $Base $Folder) $Exe))
      }
    }
    # Only direct children of Program Files (not a full-disk recursive search).
    Get-ChildItem -LiteralPath $Base -Directory -ErrorAction SilentlyContinue |
      Where-Object { $_.Name -match 'MetaTrader|Eplanet|Trading|Broker' } |
      ForEach-Object {
        foreach ($Exe in @('metaeditor64.exe','metaeditor.exe')) {
          $Candidates.Add((Join-Path $_.FullName $Exe))
        }
      }
  }
  $Editor = $null
  foreach ($Candidate in $Candidates) {
    if (Test-Path -LiteralPath $Candidate -PathType Leaf) { $Editor = (Resolve-Path -LiteralPath $Candidate).Path; break }
  }
  if (-not $Editor) { throw 'METAEDITOR_NOT_FOUND; pass -MetaEditorPath with actual metaeditor64.exe path' }
  $Receipt.metaeditor_path = $Editor

  # Copy into an isolated application-data folder. Never replace the owner's EA.
  Copy-Item -LiteralPath $SourcePath -Destination $CopiedSource -Force
  if (((Get-FileHash -LiteralPath $CopiedSource -Algorithm SHA256).Hash.ToLowerInvariant()) -ne $ExpectedSourceSHA256) {
    throw 'ISOLATED_SOURCE_COPY_MISMATCH'
  }
  foreach ($File in @($LogPath, $OutPath)) {
    if (Test-Path -LiteralPath $File) { Remove-Item -LiteralPath $File -Force }
  }
  $Arguments = '/compile:"' + $CopiedSource + '" /log'
  $Started = Start-Process -FilePath $Editor -ArgumentList $Arguments -PassThru
  if (-not $Started.WaitForExit(120000)) { throw 'METAEDITOR_COMPILE_TIMEOUT_NOT_CONFIRMED' }
  $Receipt.compiler_exit_code = $Started.ExitCode
  if (-not (Test-Path -LiteralPath $LogPath -PathType Leaf)) { throw 'COMPILER_LOG_NOT_CREATED' }
  $Receipt.log_sha256 = (Get-FileHash -LiteralPath $LogPath -Algorithm SHA256).Hash.ToLowerInvariant()
  $LogBody = Get-Content -LiteralPath $LogPath -Raw -ErrorAction Stop
  $BadErrors = [regex]::IsMatch($LogBody, '(?im)(?<!\d)[1-9]\d*\s+errors?\b')
  $ZeroErrors = [regex]::IsMatch($LogBody, '(?im)(?<!\d)0\s+errors?\b')
  $Receipt.log_reports_zero_errors = $ZeroErrors
  $Receipt.log_reports_errors = $BadErrors
  if ($BadErrors -or -not $ZeroErrors) { throw 'COMPILER_LOG_DID_NOT_CONFIRM_ZERO_ERRORS' }
  if (-not (Test-Path -LiteralPath $OutPath -PathType Leaf)) { throw 'EX5_NOT_CREATED' }
  $Ex5 = Get-Item -LiteralPath $OutPath
  if ($Ex5.Length -le 0) { throw 'EX5_EMPTY' }
  $Receipt.ex5_sha256 = (Get-FileHash -LiteralPath $OutPath -Algorithm SHA256).Hash.ToLowerInvariant()
  $Receipt.status = 'COMPILE_CONFIRMED_LOCAL_METAEDITOR_ONLY'
  $Success = $true
} catch {
  $Receipt.status = 'BLOCKED_NOT_COMPILED'
  $Receipt.error = $_.Exception.Message
} finally {
  if (-not (Test-Path -LiteralPath $Root)) { New-Item -Path $Root -ItemType Directory -Force | Out-Null }
  $Receipt | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath $ReceiptPath -Encoding UTF8
  Write-Host ('RESULT: ' + $Receipt.status)
  if ($Receipt.error) { Write-Host ('CAUSE: ' + $Receipt.error) }
  Write-Host ('REPORT: ' + $ReceiptPath)
  Write-Host 'This tool does not install, attach, run or trade using the EA.'
}
if ($Success) { exit 0 } else { exit 1 }