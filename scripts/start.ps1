param(
    [ValidateRange(1, 65535)]
    [int]$Port = 4173,
    [string]$Address = "127.0.0.1",
    [switch]$OpenBrowser,
    [switch]$Live
)

$ErrorActionPreference = "Stop"
$repoRoot = Split-Path -Parent $PSScriptRoot
$serverScript = Join-Path $PSScriptRoot "serve.py"
$venvPython = Join-Path $repoRoot ".venv\Scripts\python.exe"
$serverArgs = @($serverScript, "--host", $Address, "--port", "$Port")
if ($OpenBrowser) {
    $serverArgs += "--open"
}
if ($Live) {
    $serverArgs += @("--refresh-hours", "6")
}

if (Test-Path -LiteralPath $venvPython) {
    & $venvPython @serverArgs
} elseif (Get-Command python -ErrorAction SilentlyContinue) {
    & python @serverArgs
} elseif (Get-Command py -ErrorAction SilentlyContinue) {
    & py -3 @serverArgs
} else {
    throw "Python was not found. Install Python 3.11 or newer, then run python scripts/serve.py."
}
exit $LASTEXITCODE
