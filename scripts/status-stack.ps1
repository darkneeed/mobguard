Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

& python -m scripts.dev_stack status @args
exit $LASTEXITCODE
