# Explicit local invocation only. Does not start or modify Hookshot.
param(
    [Parameter(Mandatory=$true)][string]$Source,
    [Parameter(Mandatory=$true)][string]$Output,
    [Parameter(Mandatory=$true)][switch]$SessionClosed,
    [switch]$Visual
)
$ErrorActionPreference = 'Stop'
if (-not $SessionClosed) { throw 'Close the session and explicitly pass -SessionClosed.' }
$sourcePath = (Resolve-Path -LiteralPath $Source).Path
$outputPath = $ExecutionContext.SessionState.Path.GetUnresolvedProviderPathFromPSPath($Output)
Push-Location (Split-Path $PSScriptRoot -Parent)
try {
    $arguments = @('-3', '-m', 'vgi', 'accept', $sourcePath, '--session-closed', '--out', $outputPath)
    if ($Visual) { $arguments += '--visual' }
    & py @arguments
    if ($LASTEXITCODE -ne 0) { throw 'Acceptance failed; inspect the VGI error above.' }
} finally { Pop-Location }
