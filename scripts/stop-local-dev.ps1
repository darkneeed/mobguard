Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

& "$PSScriptRoot\stop-stack.ps1" @args
exit $LASTEXITCODE
