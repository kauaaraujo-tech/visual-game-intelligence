# Copies existing metrics/logs after the game is closed. Does not launch or configure it.
param(
    [Parameter(Mandatory=$true)][string]$GameDir,
    [Parameter(Mandatory=$true)][string]$SessionDir,
    [Parameter(Mandatory=$true)][switch]$SessionClosed
)
$ErrorActionPreference = 'Stop'
if (-not $SessionClosed) { throw 'Close the game and pass -SessionClosed before collecting.' }
$sourcePath = (Resolve-Path -LiteralPath $GameDir).Path
$targetPath = $ExecutionContext.SessionState.Path.GetUnresolvedProviderPathFromPSPath($SessionDir)
Push-Location (Split-Path $PSScriptRoot -Parent)
try {
    & py -3 -m vgi collect $sourcePath --out $targetPath --session-closed
    if ($LASTEXITCODE -ne 0) { throw 'Collection failed; inspect the error above.' }
} finally { Pop-Location }
