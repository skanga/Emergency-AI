@echo off
setlocal
REM Self-contained Windows installer; PowerShell reads the embedded code below.
if not "%~2"=="" (
  echo Usage: install.bat [new-folder]
  exit /b 1
)
set "EMERGENCY_INSTALLER=%~f0"
set "EMERGENCY_DESTINATION=%~1"
if not defined EMERGENCY_DESTINATION set "EMERGENCY_DESTINATION=Emergency-AI"
powershell.exe -NoProfile -ExecutionPolicy Bypass -Command "$text = [IO.File]::ReadAllText($env:EMERGENCY_INSTALLER); & ([scriptblock]::Create(($text -split '(?m)^# POWERSHELL\r?$', 2)[1])) -Destination $env:EMERGENCY_DESTINATION"
exit /b %ERRORLEVEL%

# POWERSHELL
param([string]$Destination = 'Emergency-AI')
$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'
$stage = $null
try {
    $target = $ExecutionContext.SessionState.Path.GetUnresolvedProviderPathFromPSPath($Destination)
    if (Test-Path -LiteralPath $target) { throw "Destination already exists: $target. Choose a new folder." }
    $parent = Split-Path -Parent $target
    if (-not (Test-Path -LiteralPath $parent -PathType Container)) { throw 'Parent folder must exist.' }
    if (-not (Get-Command tar.exe -ErrorAction SilentlyContinue)) { throw 'tar.exe is required (included in current Windows 10/11).' }
    $arch = $env:PROCESSOR_ARCHITECTURE
    if ($env:PROCESSOR_ARCHITEW6432) { $arch = $env:PROCESSOR_ARCHITEW6432 }
    # Pinned from the official python-build-standalone 20261110 release metadata.
    switch ($arch) {
        'AMD64' {
            $platform = 'windows-x86_64'; $triple = 'x86_64-pc-windows-msvc'
            $expected = 'e23fe5b16926de1d81661b1a97352e89fb167549c55a6825796ccd0f32ec7f1b'
        }
        'ARM64' {
            $platform = 'windows-arm64'; $triple = 'aarch64-pc-windows-msvc'
            $expected = '7122bf62a0cf601527ba62e19ca715d64db86b269765da23937e9ac7f968f39c'
        }
        default { throw "Unsupported Windows architecture: $arch" }
    }
    [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
    $stage = Join-Path $parent ('.emergency-install-' + [guid]::NewGuid().ToString('N'))
    New-Item -ItemType Directory -Path $stage | Out-Null
    Write-Host 'Downloading Emergency AI source...'
    $source = Join-Path $stage 'source.zip'
    Invoke-WebRequest -UseBasicParsing -Uri 'https://github.com/skanga/Emergency-AI/archive/refs/heads/main.zip' -OutFile $source
    Expand-Archive -LiteralPath $source -DestinationPath (Join-Path $stage 'source')
    $kit = Join-Path $stage 'source/Emergency-AI-main'
    if (-not (Test-Path -LiteralPath (Join-Path $kit 'emergency.py') -PathType Leaf) -or
        -not (Test-Path -LiteralPath (Join-Path $kit 'run.bat') -PathType Leaf)) { throw 'Source archive is incomplete.' }
    Write-Host "Downloading portable Python for $platform..."
    $asset = "cpython-3.12.16+20261110-$triple-install_only.tar.gz"
    $archive = Join-Path $stage 'python.tar.gz'
    Invoke-WebRequest -UseBasicParsing -Uri "https://github.com/astral-sh/python-build-standalone/releases/download/20261110/$asset" -OutFile $archive
    if ((Get-FileHash -LiteralPath $archive -Algorithm SHA256).Hash.ToLowerInvariant() -ne $expected) { throw 'Python checksum mismatch.' }
    $runtime = Join-Path $kit "runtime/python/$platform"
    New-Item -ItemType Directory -Path $runtime -Force | Out-Null
    & tar.exe -xzf $archive -C $runtime
    if ($LASTEXITCODE -ne 0) { throw 'Could not extract portable Python.' }
    & (Join-Path $runtime 'python/python.exe') -I -c 'import sys; assert sys.version_info >= (3, 8)'
    if ($LASTEXITCODE -ne 0) { throw 'Portable Python cannot run on this computer.' }
    @{ complete = $true; asset = $asset } | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $runtime 'installation.json') -Encoding ASCII
    # Directory.Move fails if the destination already exists, including a racing install.
    [IO.Directory]::Move($kit, $target)
    Write-Host "Installed in: $target"
    Write-Host 'Open run.bat in that folder to download optional AI components or open the included guides.'
} catch {
    Write-Error "Installation failed: $_" -ErrorAction Continue
    exit 1
} finally {
    if ($stage -and ([IO.Path]::GetDirectoryName($stage) -eq $parent) -and
        ([IO.Path]::GetFileName($stage) -like '.emergency-install-*') -and
        (Test-Path -LiteralPath $stage)) {
        Remove-Item -LiteralPath $stage -Recurse -Force
    }
}
