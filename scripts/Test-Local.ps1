# Runs only the diagnostic tool and synthetic tests. No game access or changes.
$ErrorActionPreference = 'Stop'
Push-Location (Split-Path $PSScriptRoot -Parent)
try {
    & py -3 -m vgi self-test
    if ($LASTEXITCODE -ne 0) { throw 'VGI self-test failed' }
    & py -3 -m unittest discover -s tests -v
    if ($LASTEXITCODE -ne 0) { throw 'VGI test suite failed' }
} finally { Pop-Location }
