Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

& "$PSScriptRoot\start-stack.ps1" @args
exit $LASTEXITCODE
