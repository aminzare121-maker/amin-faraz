# V13 Windows local ASR: install isolated Whisper + fetch original GitHub
# film-3 audio artifacts + verify their 18 SHA-pinned chunks + transcribe.
# This is a LOCAL Codex/PowerShell script; NOT a GitHub-hosted Action.
# Owner authorized Windows processing for Artin queue third film.
# No Windows system policy changes, no MT5, no account or source uploads.
[CmdletBinding()]
param(
    [string]$PrivateRoot = 'C:\AMIN_PRIVATE\V13',
    [ValidateSet('install','verify','run','all')]
    [string]$Phase = 'all'
)
$ErrorActionPreference='Stop'
Set-StrictMode -Version Latest
if ($env:OS -ne 'Windows_NT') { throw 'WINDOWS_LOCAL_ONLY' }
$SourceRepo = 'aminzare121-maker/amin-faraz'
$SourceRun = 42426863832
$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..\..\..')).Path
$PyScript = Join-Path $PSScriptRoot 'archive_asr_windows.py'
if (!(Test-Path -LiteralPath $PyScript -PathType Leaf)) { throw 'V13_ASR_PROGRAM_NOT_FOUND' }
$PrivateRoot = [System.IO.Path]::GetFullPath($PrivateRoot)
$RepositoryFull = [System.IO.Path]::GetFullPath($RepoRoot)
if ($PrivateRoot.StartsWith($RepositoryFull + [System.IO.Path]::DirectorySeparatorChar,
        [StringComparison]::OrdinalIgnoreCase)) {
    throw 'PRIVATE_ROOT_CANNOT_BE_INSIDE_REPOSITORY'
}
$Archives = Join-Path $PrivateRoot 'film3\original_audio_archives'
$ResultDir = Join-Path $PrivateRoot 'film3\private_asr'
$VenvDir = Join-Path $PrivateRoot 'asr-venv'
$Python = Join-Path $VenvDir 'Scripts\python.exe'
New-Item -ItemType Directory -Path $PrivateRoot -Force | Out-Null
Write-Output 'V13_FILM3_WINDOWS_LOCAL_WORKFLOW=START'
Write-Output "V13_FILM3_PRIVATE_ROOT=$PrivateRoot"

function Require-Command([string]$Command) {
    if (!(Get-Command $Command -ErrorAction SilentlyContinue)) {
        throw "MISSING_WINDOWS_TOOL_$Command"
    }
}
function Install-Venv {
    if (!(Test-Path $Python -PathType Leaf)) {
        if (Get-Command py -ErrorAction SilentlyContinue) {
            & py -3 -m venv $VenvDir
        } elseif (Get-Command python -ErrorAction SilentlyContinue) {
            & python -m venv $VenvDir
        } else { throw 'WINDOWS_PYTHON3_REQUIRED' }
        if ($LASTEXITCODE -ne 0) { throw 'WINDOWS_VENV_CREATION_FAILED' }
    }
    & $Python -m pip install --disable-pip-version-check 'faster-whisper>=1.1,<2'
    if ($LASTEXITCODE -ne 0) { throw 'FASTER_WHISPER_INSTALL_FAILED_IN_PRIVATE_VENV' }
    & $Python -c 'from faster_whisper import WhisperModel; print("V13_FASTER_WHISPER_PYTHON_IMPORT_OK")'
    if ($LASTEXITCODE -ne 0) { throw 'FASTER_WHISPER_IMPORT_FAILED' }
}
function Fetch-VerifiedArchivedAudio {
    $prefix = 'video001-artin-course-001-video-q-0003-artin-clip-01-original-audio-'
    $missing = @()
    for($i=0; $i -lt 17; $i++) {
        $w = Join-Path $Archives ('worker_{0:D2}' -f $i)
        if (!(Test-Path (Join-Path $w 'fast_av_manifest.json') -PathType Leaf)) { $missing += $i }
    }
    if ($missing.Count -gt 0) {
        Require-Command 'gh'
        & gh auth status *> $null
        if ($LASTEXITCODE -ne 0) { throw 'GITHUB_CLI_LOGIN_REQUIRED_FOR_PRIVATE_ARCHIVES_NO_TOKEN_IN_CHAT' }
        for($j=0; $j -lt $missing.Count; $j++) {
            $i = $missing[$j]
            $worker = Join-Path $Archives ('worker_{0:D2}' -f $i)
            New-Item -ItemType Directory -Path $worker -Force | Out-Null
            Write-Output ('V13_ARCHIVE_DOWNLOAD_WORKER={0}' -f $i)
            & gh run download $SourceRun --repo $SourceRepo --name ($prefix+$i) --dir $worker
            if ($LASTEXITCODE -ne 0) { throw ("GITHUB_ARCHIVE_DOWNLOAD_FAILED_WORKER_{0}" -f $i) }
        }
    }
}
function Verify-Audio {
    Require-Command 'python'
    & $Python $PyScript --archives $Archives --out $ResultDir --phase verify
    if ($LASTEXITCODE -ne 0) { throw 'FILM3_ARCHIVED_SOURCE_SHA_VERIFICATION_FAILED' }
}
if ($Phase -in @('install','all')) {
    Install-Venv
}
if ($Phase -in @('verify','run','all')) {
    if (!(Test-Path $Python -PathType Leaf)) { throw 'VENV_MISSING_USE_PHASE_INSTALL_FIRST' }
    Fetch-VerifiedArchivedAudio
    & $Python $PyScript --archives $Archives --out $ResultDir --phase verify
    if ($LASTEXITCODE -ne 0) { throw 'FILM3_18_PART_AUDIO_SHA_CHECK_FAILED' }
}
if ($Phase -in @('run','all')) {
    & $Python $PyScript --archives $Archives --out $ResultDir --phase run
    if ($LASTEXITCODE -ne 0) { throw 'ASR_INCOMPLETE_CHECKPOINTS_PRESERVED' }
}
Write-Output 'V13_FILM3_WINDOWS_LOCAL_WORKFLOW=COMPLETED_PHASE'
Write-Output ('V13_COMPLETED_PHASE=' + $Phase)
