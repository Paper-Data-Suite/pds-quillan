param(
    [string]$Python = "python",
    [Parameter(Mandatory)] [string]$PdsCore064Wheel,
    [Parameter(Mandatory)] [string]$QuillanWheel
)

$ErrorActionPreference = "Stop"
$Repository = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$CoreWheel = (Resolve-Path -LiteralPath $PdsCore064Wheel).Path
$CandidateWheel = (Resolve-Path -LiteralPath $QuillanWheel).Path
$Prefix = 'pds-quillan-issue419-wheel-'
$TemporaryRoot = Join-Path ([System.IO.Path]::GetTempPath()) ($Prefix + [guid]::NewGuid().ToString('N'))
$OriginalLocation = (Get-Location).Path

function Invoke-Required {
    param([string]$Label, [string]$Executable, [string[]]$Arguments)
    Write-Host "=== $Label ==="
    $ExistingPythonPath = $env:PYTHONPATH
    try {
        Remove-Item Env:PYTHONPATH -ErrorAction SilentlyContinue
        & $Executable @Arguments
        $Code = $LASTEXITCODE
    }
    finally {
        if ($null -eq $ExistingPythonPath) {
            Remove-Item Env:PYTHONPATH -ErrorAction SilentlyContinue
        }
        else { $env:PYTHONPATH = $ExistingPythonPath }
    }
    if ($Code -ne 0) { throw "$Label failed with exit code $Code" }
}

$PythonExe = (Get-Command $Python -ErrorAction Stop).Source
$Version = '0.10.5'
$ExpectedLeaf = "quillan-$Version-py3-none-any.whl"
if ((Split-Path $CandidateWheel -Leaf) -ne $ExpectedLeaf) {
    throw "Expected the exact Quillan candidate wheel $ExpectedLeaf"
}

try {
    New-Item -ItemType Directory -Path $TemporaryRoot | Out-Null
    $Environment = Join-Path $TemporaryRoot 'venv'
    $Outside = Join-Path $TemporaryRoot 'outside-source'
    $Workspace = Join-Path $TemporaryRoot 'issue419-workspace'
    New-Item -ItemType Directory -Path $Outside | Out-Null

    Invoke-Required 'Verify released Core 0.6.4 wheel' $PythonExe @(
        (Join-Path $PSScriptRoot 'verify_core_wheel.py'), $CoreWheel,
        '--core-version', '0.6.4'
    )
    Invoke-Required 'Create isolated Python environment' $PythonExe @(
        '-m', 'venv', $Environment
    )
    $EnvironmentPython = Join-Path $Environment 'Scripts\python.exe'
    Invoke-Required 'Install exact released Core wheel' $EnvironmentPython @(
        '-m', 'pip', 'install', $CoreWheel
    )
    Invoke-Required 'Verify installed released Core wheel' $EnvironmentPython @(
        (Join-Path $PSScriptRoot 'verify_core_wheel.py'), $CoreWheel,
        '--core-version', '0.6.4', '--verify-installed'
    )
    Invoke-Required 'Install exact Quillan wheel' $EnvironmentPython @(
        '-m', 'pip', 'install', $CandidateWheel
    )
    Invoke-Required 'Check installed dependencies' $EnvironmentPython @('-m', 'pip', 'check')
    Push-Location $Outside
    try {
        Invoke-Required 'Issue #419 independent installed end-to-end acceptance' `
            $EnvironmentPython @(
                (Join-Path $PSScriptRoot 'verify_installed_issue419_recovery.py'),
                '--workspace', $Workspace,
                '--repository', $Repository,
                '--expected-quillan-version', $Version,
                '--expected-core-version', '0.6.4'
            )
    }
    finally { Pop-Location }
}
finally {
    Set-Location $OriginalLocation
    if (Test-Path -LiteralPath $TemporaryRoot) {
        $Resolved = (Resolve-Path -LiteralPath $TemporaryRoot).Path
        $Temp = [System.IO.Path]::GetFullPath([System.IO.Path]::GetTempPath()).TrimEnd('\')
        $UserProfilePath = [Environment]::GetFolderPath('UserProfile')
        if (-not $Resolved.StartsWith($Temp + '\') -or
            -not (Split-Path $Resolved -Leaf).StartsWith($Prefix) -or
            $Resolved -eq $Repository -or $Resolved -eq $UserProfilePath -or
            $Resolved -eq [System.IO.Path]::GetPathRoot($Resolved).TrimEnd('\')) {
            throw "Refusing unsafe acceptance cleanup: $Resolved"
        }
        $Object = Get-Item -LiteralPath $Resolved -Force
        if ($Object.LinkType) { throw "Refusing linked acceptance cleanup root: $Resolved" }
        Remove-Item -LiteralPath $Resolved -Recurse -Force
    }
}
