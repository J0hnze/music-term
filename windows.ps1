[CmdletBinding()]
param(
    [ValidateSet('setup', 'start', 'check')][string]$Mode = 'start',
    [string]$Distribution = 'Ubuntu',
    [ValidateSet('auto', 'blocks', 'sixel', 'kitty')][string]$Artwork = $(if ($env:MUSIC_TERM_ARTWORK) { $env:MUSIC_TERM_ARTWORK } else { 'auto' }),
    [switch]$Dev,
    [switch]$TestArtwork
)
$ErrorActionPreference = 'Stop'
try {
    if ($Mode -eq 'setup') {
        if (-not (Get-Command wt.exe -ErrorAction SilentlyContinue)) {
            if (-not (Get-Command winget.exe -ErrorAction SilentlyContinue)) {
                throw 'Install Windows Terminal and App Installer from Microsoft Store, then rerun setup.bat.'
            }
            & winget.exe install --id Microsoft.WindowsTerminal --exact --accept-package-agreements --accept-source-agreements
            if ($LASTEXITCODE -ne 0) { throw 'Windows Terminal installation failed.' }
        }
        if (-not (Get-Command wsl.exe -ErrorAction SilentlyContinue)) {
            throw 'Run setup.bat from administrator PowerShell after enabling WSL: wsl --install -d Ubuntu. Restart if requested, create your Ubuntu user, then rerun setup.bat.'
        }
        $distributions = ((& wsl.exe --list --quiet) -join "`n") -replace "`0", ''
        if ($LASTEXITCODE -ne 0 -or $Distribution -notin ($distributions -split "`n" | ForEach-Object { $_.Trim() })) {
            & wsl.exe --install --distribution $Distribution --no-launch
            if ($LASTEXITCODE -ne 0) { throw 'WSL installation needs administrator PowerShell. Rerun setup.bat there, then restart if requested.' }
            throw "Installed '$Distribution'. Open it to create your Linux user, then rerun setup.bat."
        }
        & wsl.exe --update
        if ($LASTEXITCODE -ne 0) { throw 'WSL update failed. Run wsl --update from administrator PowerShell, then rerun setup.bat.' }
    }
    if (-not (Get-Command wsl.exe -ErrorAction SilentlyContinue)) {
        throw 'WSL is required. In administrator PowerShell run: wsl --install -d Ubuntu. Restart and finish Ubuntu user setup, then retry.'
    }
    $scriptPath = Join-Path $PSScriptRoot 'tools/windows-wsl.sh'
    $linuxScript = & wsl.exe --distribution $Distribution --exec wslpath -a $scriptPath
    if ($LASTEXITCODE -ne 0 -or -not $linuxScript) {
        throw "Could not open WSL distribution '$Distribution'. Run wsl --list --verbose and finish its first-run setup."
    }
    $linuxScript = ($linuxScript | Out-String).Trim()
    $devFlag = if ($Dev) { 'dev' } else { 'runtime' }
    $debugFlag = if ($PSBoundParameters.ContainsKey('Debug') -and $PSBoundParameters['Debug']) { 'debug' } else { 'normal' }
    $testFlag = if ($TestArtwork) { 'test-artwork' } else { 'player' }
    & wsl.exe --distribution $Distribution --exec bash $linuxScript $Mode $devFlag $Artwork $debugFlag $testFlag
    exit $LASTEXITCODE
} catch {
    Write-Host $_.Exception.Message -ForegroundColor Red
    exit 1
}
