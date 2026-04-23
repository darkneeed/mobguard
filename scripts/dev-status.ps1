Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

& "$PSScriptRoot\status-stack.ps1" @args
exit $LASTEXITCODE
