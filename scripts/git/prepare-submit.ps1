param(
    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]]$CommitShas
)

$guardScript = Join-Path $PSScriptRoot 'git-guard.ps1'
& $guardScript prepare-submit @CommitShas
exit $LASTEXITCODE
