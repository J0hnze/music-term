[CmdletBinding()]
param(
    [ValidateSet('setup', 'start', 'check')][string]$Mode = 'start',
    [ValidateSet('auto', 'blocks', 'sixel', 'kitty')][string]$Artwork = $(if ($env:MUSIC_TERM_ARTWORK) { $env:MUSIC_TERM_ARTWORK } else { 'auto' }),
    [switch]$Dev,
    [switch]$TestArtwork
)
$ErrorActionPreference = 'Stop'

function Update-ToolPath {
    $paths = @($env:PATH, [Environment]::GetEnvironmentVariable('PATH', 'User'), [Environment]::GetEnvironmentVariable('PATH', 'Machine'),
        "$env:LOCALAPPDATA\Microsoft\WinGet\Links", "$env:USERPROFILE\.local\bin", "$env:USERPROFILE\.deno\bin")
    $env:PATH = ($paths | Where-Object { $_ }) -join ';'
}

function Install-Tool([string]$Command, [string]$Package) {
    if (Get-Command $Command -ErrorAction SilentlyContinue) { return }
    if (-not (Get-Command winget.exe -ErrorAction SilentlyContinue)) {
        throw 'Install App Installer from Microsoft Store to provide winget, then rerun win_setup.bat.'
    }
    & winget.exe install --id $Package --exact --source winget --accept-package-agreements --accept-source-agreements
    if ($LASTEXITCODE -ne 0) { throw "Could not install $Package. Resolve the winget error, then rerun win_setup.bat." }
    Update-ToolPath
    if (-not (Get-Command $Command -ErrorAction SilentlyContinue)) {
        throw "$Package was installed, but is not on PATH yet. Open a new terminal and rerun win_setup.bat."
    }
}

try {
    Set-Location -LiteralPath $PSScriptRoot
    Update-ToolPath
    $env:UV_PROJECT_ENVIRONMENT = Join-Path $PSScriptRoot '.venv-win'
    $env:MUSIC_TERM_ARTWORK = $Artwork
    if ($Mode -eq 'setup') {
        Install-Tool 'wt.exe' 'Microsoft.WindowsTerminal'
        Install-Tool 'uv.exe' 'astral-sh.uv'
        Install-Tool 'mpv' 'shinchiro.mpv'
        Install-Tool 'ffmpeg' 'Gyan.FFmpeg'
        Install-Tool 'deno' 'DenoLand.Deno'
        $syncArgs = @('sync', '--locked', '--python', '3.12')
        if ($Dev) { $syncArgs += @('--extra', 'dev') }
        & uv.exe @syncArgs
        if ($LASTEXITCODE -ne 0) { throw 'Python dependency installation failed.' }
    } elseif (-not (Get-Command uv.exe -ErrorAction SilentlyContinue) -or -not (Test-Path -LiteralPath "$env:UV_PROJECT_ENVIRONMENT\Scripts\python.exe")) {
        throw 'Run win_setup.bat first to install the native Windows environment.'
    }
    $runArgs = @('run', '--locked', '--no-sync', 'music-term', '--artwork', $Artwork)
    if ($PSBoundParameters.ContainsKey('Debug') -and $PSBoundParameters['Debug']) { $runArgs += '--debug' }
    if ($Mode -in @('setup', 'check')) { $runArgs += '--check' }
    elseif ($TestArtwork) { $runArgs += '--test-artwork' }
    & uv.exe @runArgs
    $result = $LASTEXITCODE
    if ($Mode -eq 'setup' -and $result -eq 0) { Write-Host 'Native Windows setup complete. Run win_start.bat.' }
    exit $result
} catch {
    Write-Host $_.Exception.Message -ForegroundColor Red
    exit 1
}