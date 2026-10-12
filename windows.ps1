[CmdletBinding()]
param(
    [ValidateSet('setup', 'start', 'check')][string]$Mode = 'start',
    [string]$Distribution = 'Ubuntu',
    [ValidateSet('auto', 'blocks', 'sixel', 'kitty')][string]$Artwork = $(if ($env:MUSIC_TERM_ARTWORK) { $env:MUSIC_TERM_ARTWORK } else { 'auto' }),
    [switch]$Dev
)
$ErrorActionPreference = 'Stop'
try {
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
    & wsl.exe --distribution $Distribution --exec bash $linuxScript $Mode $devFlag $Artwork
    exit $LASTEXITCODE
} catch {
    Write-Host $_.Exception.Message -ForegroundColor Red
    exit 1
}
