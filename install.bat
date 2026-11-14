@echo off
setlocal
REM Self-contained Windows installer; PowerShell reads the embedded code below.
if not "%~2"=="" (
  echo Usage: install.bat [new-folder]
  exit /b 1
)
set "EMERGENCY_INSTALLER=%~f0"
set "EMERGENCY_DESTINATION=%~1"
powershell.exe -NoProfile -ExecutionPolicy Bypass -Command "$text = [IO.File]::ReadAllText($env:EMERGENCY_INSTALLER); & ([scriptblock]::Create(($text -split '(?m)^# POWERSHELL\r?$', 2)[1])) -Destination $env:EMERGENCY_DESTINATION"
exit /b %ERRORLEVEL%

# POWERSHELL
param([string]$Destination = 'Emergency-AI')
$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'
$stage = $null
$moved = @()
$activated = $false
$log = $null
function Fetch-Archive($Uri, $OutFile, [bool]$Resume = $false) {
    for ($attempt = 1; $attempt -le 3; $attempt++) {
        $message = "Downloading $(Split-Path -Leaf $OutFile), attempt $attempt/3"
        Write-Host $message
        Add-Content -LiteralPath $log -Value "$(Get-Date -Format o) $message : $Uri"
        $options = @('--fail', '--location', '--connect-timeout', '30', '--speed-time', '60', '--speed-limit', '1', '--proto', '=https', '--proto-redir', '=https')
        if ($Resume) { $options += @('-C', '-') }
        $savedPreference = $ErrorActionPreference
        $ErrorActionPreference = 'Continue'
        & curl.exe @options -o $OutFile $Uri 2>> $log
        $code = $LASTEXITCODE
        $ErrorActionPreference = $savedPreference
        if ($code -eq 0) {
            Write-Host "Download complete: $((Get-Item -LiteralPath $OutFile).Length) bytes"
            return
        }
        Add-Content -LiteralPath $log -Value "curl exit code: $code"
        if ($code -in @(33, 36)) {
            Remove-Item -LiteralPath $OutFile -Force -ErrorAction SilentlyContinue
        }
        if ($attempt -lt 3) { Start-Sleep -Seconds 1 }
    }
    throw "Download failed after three attempts. Download files retained for retry"
}
function Assert-InstallDestination($Path) {
    if (-not (Test-Path -LiteralPath $Path)) { return }
    $item = Get-Item -LiteralPath $Path -Force
    if (-not $item.PSIsContainer -or ($item.Attributes -band [IO.FileAttributes]::ReparsePoint)) {
        throw "Destination must be a regular folder: $Path"
    }
    foreach ($child in Get-ChildItem -LiteralPath $Path -Force) {
        if ($child.PSIsContainer -or ($child.Attributes -band [IO.FileAttributes]::ReparsePoint) -or
            $child.Name -notin @('install.bat', 'install.sh', '.DS_Store', 'Thumbs.db')) {
            throw "Destination contains existing files: $Path. Choose an empty folder."
        }
    }
}
try {
    if (-not $Destination) {
        $Destination = if ((Split-Path -Leaf (Get-Location).Path) -eq 'Emergency-AI') { '.' } else { 'Emergency-AI' }
    }
    $target = $ExecutionContext.SessionState.Path.GetUnresolvedProviderPathFromPSPath($Destination)
    Assert-InstallDestination $target
    $parent = Split-Path -Parent $target
    if (-not (Test-Path -LiteralPath $parent -PathType Container)) { throw 'Parent folder must exist.' }
    if (-not (Get-Command tar.exe -ErrorAction SilentlyContinue)) { throw 'tar.exe is required (included in current Windows 10/11).' }
    if (-not (Get-Command curl.exe -ErrorAction SilentlyContinue)) { throw 'curl.exe is required (included in current Windows 10/11).' }
    $cache = Join-Path $parent ('.' + (Split-Path -Leaf $target) + '-downloads')
    if ((Test-Path -LiteralPath $cache) -and ((Get-Item -LiteralPath $cache -Force).Attributes -band [IO.FileAttributes]::ReparsePoint)) { throw 'Download cache must not be a link.' }
    New-Item -ItemType Directory -Path $cache -Force | Out-Null
    $log = Join-Path $cache 'install.log'
    Write-Host "Installation log: $log"
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
    Fetch-Archive 'https://github.com/skanga/Emergency-AI/archive/refs/heads/main.zip' $source
    Expand-Archive -LiteralPath $source -DestinationPath (Join-Path $stage 'source')
    $kit = Join-Path $stage 'source/Emergency-AI-main'
    if (-not (Test-Path -LiteralPath (Join-Path $kit 'emergency.py') -PathType Leaf) -or
        -not (Test-Path -LiteralPath (Join-Path $kit 'run.bat') -PathType Leaf)) { throw 'Source archive is incomplete.' }
    Write-Host "Downloading portable Python for $platform..."
    $asset = "cpython-3.12.16+20261110-$triple-install_only.tar.gz"
    $archive = Join-Path $cache "$asset.part"
    if ((Test-Path -LiteralPath $archive) -and (Get-FileHash -LiteralPath $archive -Algorithm SHA256).Hash.ToLowerInvariant() -eq $expected) {
        Write-Host 'Reusing verified portable Python download.'
    } else {
        Fetch-Archive "https://github.com/astral-sh/python-build-standalone/releases/download/20261110/$asset" $archive $true
    }
    if ((Get-FileHash -LiteralPath $archive -Algorithm SHA256).Hash.ToLowerInvariant() -ne $expected) {
        Remove-Item -LiteralPath $archive -Force
        throw 'Python checksum mismatch. Invalid download removed; rerun the installer.'
    }
    $runtime = Join-Path $kit "runtime/python/$platform"
    New-Item -ItemType Directory -Path $runtime -Force | Out-Null
    & tar.exe -xzf $archive -C $runtime
    if ($LASTEXITCODE -ne 0) { throw 'Could not extract portable Python.' }
    & (Join-Path $runtime 'python/python.exe') -I -c 'import sys; assert sys.version_info >= (3, 8)'
    if ($LASTEXITCODE -ne 0) { throw 'Portable Python cannot run on this computer.' }
    @{ complete = $true; asset = $asset } | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $runtime 'installation.json') -Encoding ASCII
    Assert-InstallDestination $target
    if (Test-Path -LiteralPath $target) {
        foreach ($child in Get-ChildItem -LiteralPath $kit -Force) {
            $path = Join-Path $target $child.Name
            # Keep the downloaded installers, including the batch file running now.
            if ($child.Name -in @('install.bat', 'install.sh') -and (Test-Path -LiteralPath $path)) { continue }
            if ($child.PSIsContainer) { [IO.Directory]::Move($child.FullName, $path) }
            else { [IO.File]::Move($child.FullName, $path) }
            $moved += $path
        }
    } else {
        [IO.Directory]::Move($kit, $target)
    }
    $activated = $true
    Write-Host "Installed in: $target"
    Write-Host 'Open run.bat in that folder to download optional AI components or open the included guides.'
} catch {
    if ($log) { Add-Content -LiteralPath $log -Value $_.Exception.Message }
    foreach ($path in $moved) {
        if ([IO.Path]::GetDirectoryName($path) -eq $target) {
            Move-Item -LiteralPath $path -Destination $kit
        }
    }
    [Console]::Error.WriteLine("Installation failed: " + $_.Exception.Message + ". Retry install.bat after correcting the problem. Log: $log")
    exit 1
} finally {
    if ($stage -and ([IO.Path]::GetDirectoryName($stage) -eq $parent) -and
        ([IO.Path]::GetFileName($stage) -like '.emergency-install-*') -and
        (Test-Path -LiteralPath $stage)) {
        Remove-Item -LiteralPath $stage -Recurse -Force
    }
}
if (-not [Console]::IsInputRedirected) {
    $answer = Read-Host 'Run first-time setup now (run.bat prepare)? [Y/n]'
    if ([string]::IsNullOrEmpty($answer) -or $answer -match '^(?i:y|yes)$') {
        & (Join-Path $target 'run.bat') prepare
        if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
        $open = Read-Host 'Open Emergency AI now? [Y/n]'
        if ([string]::IsNullOrEmpty($open) -or $open -match '^(?i:y|yes)$') {
            & (Join-Path $target 'run.bat')
            exit $LASTEXITCODE
        }
    }
}
