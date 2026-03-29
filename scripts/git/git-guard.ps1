param(
    [Parameter(Position = 0, Mandatory = $true)]
    [string]$Action,
    [string]$RemoteName,
    [string]$RemoteUrl,
    [string]$StdinFile,
    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]]$CommitShas
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

$allowedActions = @('hook-pre-commit', 'hook-pre-push', 'prepare-submit')
if ($Action -notin $allowedActions) {
    throw "Unsupported action: $Action"
}

$CommitShas = @($CommitShas | Where-Object { $_ -and $_.Trim() })

function Invoke-Git {
    param(
        [Parameter(ValueFromRemainingArguments = $true)]
        [string[]]$Args
    )

    $result = Invoke-GitProcess @Args
    if ($result.ExitCode -ne 0) {
        $message = if ($result.Output) { ($result.Output -join "`n") } else { '' }
        throw "git $($Args -join ' ') failed.`n$message"
    }

    return $result.Output
}

function Invoke-GitAllowFail {
    param(
        [Parameter(ValueFromRemainingArguments = $true)]
        [string[]]$Args
    )

    return Invoke-GitProcess @Args
}

function Invoke-GitProcess {
    param(
        [Parameter(ValueFromRemainingArguments = $true)]
        [string[]]$Args
    )

    $stdoutFile = Join-Path ([System.IO.Path]::GetTempPath()) ([System.Guid]::NewGuid().ToString('N') + '.stdout')
    $stderrFile = Join-Path ([System.IO.Path]::GetTempPath()) ([System.Guid]::NewGuid().ToString('N') + '.stderr')

    try {
        $process = Start-Process -FilePath 'git' -ArgumentList $Args -NoNewWindow -Wait -PassThru -RedirectStandardOutput $stdoutFile -RedirectStandardError $stderrFile
        $output = @()
        if (Test-Path $stdoutFile) {
            $output += @(Get-Content $stdoutFile)
        }
        if (Test-Path $stderrFile) {
            $output += @(Get-Content $stderrFile)
        }

        return @{
            ExitCode = $process.ExitCode
            Output   = @($output | Where-Object { $_ -ne $null })
        }
    }
    finally {
        Remove-Item $stdoutFile, $stderrFile -ErrorAction SilentlyContinue
    }
}

function Get-RepoRoot {
    return (Invoke-Git rev-parse --show-toplevel | Select-Object -First 1).Trim()
}

function Get-CurrentBranch {
    $result = Invoke-GitAllowFail symbolic-ref --quiet --short HEAD
    if ($result.ExitCode -ne 0) {
        return ''
    }

    return ($result.Output | Select-Object -First 1).Trim()
}

function Test-IsZeroSha {
    param([string]$Sha)
    return $Sha -match '^0{40}$'
}

function Get-BranchNameFromRef {
    param([string]$Ref)

    if ($Ref -eq 'HEAD') {
        return Get-CurrentBranch
    }

    if ($Ref -like 'refs/heads/*') {
        return $Ref.Substring('refs/heads/'.Length)
    }

    return $Ref
}

function Assert {
    param(
        [bool]$Condition,
        [string]$Message
    )

    if (-not $Condition) {
        throw $Message
    }
}

function Test-RefIsAncestor {
    param(
        [string]$Ancestor,
        [string]$Descendant
    )

    $result = Invoke-GitAllowFail merge-base --is-ancestor $Ancestor $Descendant
    return $result.ExitCode -eq 0
}

function Get-CommitBody {
    param([string]$Commit)

    return (Invoke-Git log -1 '--format=%B' $Commit) -join "`n"
}

function Get-CommitList {
    param(
        [string]$Base,
        [string]$Tip
    )

    $output = Invoke-Git rev-list --reverse "$Base..$Tip"
    return @($output | Where-Object { $_ -and $_.Trim() })
}

function Test-SubmitRange {
    param([string]$Tip)

    $baseRef = 'refs/remotes/upstream/main'
    $baseExists = Invoke-GitAllowFail rev-parse --verify "$baseRef^{commit}"
    Assert ($baseExists.ExitCode -eq 0) 'Missing refs/remotes/upstream/main. Run git fetch upstream main first.'
    Assert (Test-RefIsAncestor $baseRef $Tip) 'codex/submit must be rebuilt from upstream/main.'

    $commits = Get-CommitList -Base $baseRef -Tip $Tip
    Assert ($commits.Count -gt 0) 'codex/submit does not contain any submit commits.'

    foreach ($commit in $commits) {
        $parentsLine = (Invoke-Git rev-list --parents -n 1 $commit | Select-Object -First 1).Trim()
        $parentCount = ($parentsLine -split ' ').Count - 1
        Assert ($parentCount -le 1) "Submit commit $commit must not be a merge commit."

        $body = Get-CommitBody -Commit $commit
        $match = [regex]::Match($body, 'cherry picked from commit ([0-9a-fA-F]{7,40})')
        Assert ($match.Success) "Submit commit $commit is missing '(cherry picked from commit ...)' metadata."

        $sourceSha = $match.Groups[1].Value
        $sourceExists = Invoke-GitAllowFail rev-parse --verify "$sourceSha^{commit}"
        Assert ($sourceExists.ExitCode -eq 0) "Source commit $sourceSha referenced by $commit does not exist locally."
        Assert (Test-RefIsAncestor $sourceSha 'refs/heads/main') "Source commit $sourceSha referenced by $commit is not contained in local main."
    }
}

function Invoke-PreCommitGuard {
    $branch = Get-CurrentBranch
    if ($branch -eq 'codex/submit' -and $env:CSA_ALLOW_GENERATED_SUBMIT -ne '1') {
        throw 'Direct commits on codex/submit are blocked. Use scripts\git\prepare-submit.cmd <sha1> <sha2> ... instead.'
    }
}

function Invoke-PrePushGuard {
    Assert ([string]::IsNullOrWhiteSpace($RemoteName) -eq $false) 'pre-push hook missing remote name.'
    Assert ([string]::IsNullOrWhiteSpace($StdinFile) -eq $false) 'pre-push hook missing stdin file.'

    $lines = @()
    if (Test-Path $StdinFile) {
        $lines = @(Get-Content $StdinFile | Where-Object { $_ -and $_.Trim() })
    }

    foreach ($line in $lines) {
        $parts = $line -split ' '
        Assert ($parts.Count -ge 4) "Unexpected pre-push payload: $line"

        $localRef = $parts[0]
        $localSha = $parts[1]
        $remoteRef = $parts[2]
        $remoteSha = $parts[3]

        if ($RemoteName -eq 'upstream') {
            throw 'Direct pushes to upstream are blocked. Push to origin first and open a PR from codex/submit.'
        }

        if (Test-IsZeroSha $localSha) {
            continue
        }

        if ($remoteRef -notlike 'refs/heads/*') {
            continue
        }

        $targetBranch = Get-BranchNameFromRef -Ref $remoteRef
        $sourceBranch = Get-BranchNameFromRef -Ref $localRef

        switch -Wildcard ($targetBranch) {
            'main' {
                Assert ($RemoteName -eq 'origin') 'main can only be pushed to origin.'
                Assert ($sourceBranch -eq 'main') 'main can only be pushed from local main.'
                continue
            }
            'codex/submit' {
                Assert ($RemoteName -eq 'origin') 'codex/submit can only be pushed to origin.'
                Test-SubmitRange -Tip $localSha
                continue
            }
            'codex/wip-*' {
                Assert ($RemoteName -eq 'origin') 'codex/wip-* branches can only be pushed to origin.'
                Assert ($sourceBranch -eq $targetBranch) "Push $targetBranch from the matching local branch."
                continue
            }
            default {
                throw "Pushes to $targetBranch are blocked by the local workflow guard."
            }
        }
    }
}

function Invoke-PrepareSubmit {
    param([string[]]$Shas)

    Assert ($Shas.Count -gt 0) 'Usage: scripts\git\prepare-submit.cmd <sha1> <sha2> ...'

    foreach ($sha in $Shas) {
        $verify = Invoke-GitAllowFail rev-parse --verify "$sha^{commit}"
        Assert ($verify.ExitCode -eq 0) "Unknown commit: $sha"
        Assert (Test-RefIsAncestor $sha 'refs/heads/main') "Commit $sha is not contained in local main."
    }

    Invoke-Git fetch --prune origin
    Invoke-Git fetch --prune upstream

    $tempRoot = Join-Path ([System.IO.Path]::GetTempPath()) ([System.Guid]::NewGuid().ToString('N'))
    $null = New-Item -ItemType Directory -Path $tempRoot -Force

    try {
        Invoke-Git worktree add --detach $tempRoot refs/remotes/upstream/main

        Copy-Item -Recurse -Force (Join-Path $repoRoot '.githooks') (Join-Path $tempRoot '.githooks')
        $tempScriptsRoot = Join-Path $tempRoot 'scripts'
        if (-not (Test-Path $tempScriptsRoot)) {
            $null = New-Item -ItemType Directory -Path $tempScriptsRoot -Force
        }
        Copy-Item -Recurse -Force (Join-Path $repoRoot 'scripts\git') (Join-Path $tempScriptsRoot 'git')

        $env:CSA_ALLOW_GENERATED_SUBMIT = '1'

        foreach ($sha in $Shas) {
            $pickResult = Invoke-GitAllowFail -C $tempRoot cherry-pick -x $sha
            if ($pickResult.ExitCode -ne 0) {
                $message = if ($pickResult.Output) { ($pickResult.Output -join "`n") } else { '' }
                throw "Failed to cherry-pick $sha onto codex/submit.`n$message"
            }
        }

        $submitSha = (Invoke-Git -C $tempRoot rev-parse HEAD | Select-Object -First 1).Trim()

        $currentLocation = Get-Location
        try {
            Set-Location $tempRoot
            Test-SubmitRange -Tip $submitSha
        }
        finally {
            Set-Location $currentLocation
        }

        $pushResult = Invoke-GitAllowFail -C $tempRoot push --force-with-lease origin "HEAD:refs/heads/codex/submit"
        if ($pushResult.ExitCode -ne 0) {
            $message = if ($pushResult.Output) { ($pushResult.Output -join "`n") } else { '' }
            throw "Failed to push generated codex/submit.`n$message"
        }

        $branchUpdate = Invoke-GitAllowFail branch -f codex/submit $submitSha
        if ($branchUpdate.ExitCode -ne 0) {
            Write-Warning 'Generated codex/submit was pushed, but the local codex/submit branch could not be moved automatically.'
            Write-Warning (($branchUpdate.Output -join "`n").Trim())
        }

        Write-Host "Generated codex/submit at $submitSha"
    }
    finally {
        Remove-Item Env:CSA_ALLOW_GENERATED_SUBMIT -ErrorAction SilentlyContinue

        $removeResult = Invoke-GitAllowFail worktree remove --force $tempRoot
        if ($removeResult.ExitCode -ne 0) {
            Write-Warning (($removeResult.Output -join "`n").Trim())
        }

        if (Test-Path $tempRoot) {
            Remove-Item -Recurse -Force $tempRoot -ErrorAction SilentlyContinue
        }
    }
}

$repoRoot = Get-RepoRoot
Set-Location $repoRoot

switch ($Action) {
    'hook-pre-commit' { Invoke-PreCommitGuard }
    'hook-pre-push' { Invoke-PrePushGuard }
    'prepare-submit' { Invoke-PrepareSubmit -Shas $CommitShas }
}
