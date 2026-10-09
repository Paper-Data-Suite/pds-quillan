param(
    [string]$Python = "python",
    [Parameter(Mandatory)] [string]$PdsCore065Wheel,
    [Parameter(Mandatory)] [string]$ArtifactOutputDirectory,
    [switch]$SkipRepositoryDevelopmentChecks
)

$ErrorActionPreference = "Stop"
$Repository = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot "..")).Path
$PythonExe = (Get-Command $Python -ErrorAction Stop).Source
$CoreWheel = (Resolve-Path -LiteralPath $PdsCore065Wheel).Path
$ArtifactOut = [System.IO.Path]::GetFullPath($ArtifactOutputDirectory)
$Prefix = "pds-quillan-v0106-"
$TempRoot = Join-Path ([System.IO.Path]::GetTempPath()) ($Prefix + [guid]::NewGuid().ToString('N'))
$WheelName = "quillan-0.10.6-py3-none-any.whl"
$SdistName = "quillan-0.10.6.tar.gz"
$Artifacts = Join-Path $TempRoot "artifacts"
$Environment = Join-Path $TempRoot "venv"
$Outside = Join-Path $TempRoot "outside-source"
$Work = Join-Path $TempRoot "application"
$RecoveryWork = Join-Path $TempRoot "scan-recovery"
$InstalledPython = Join-Path $Environment 'Scripts\python.exe'

function Invoke-Required {
    param([string]$Label, [string]$Executable, [string[]]$Arguments)
    Write-Host "=== $Label ==="
    $PriorPythonPath = $env:PYTHONPATH
    try {
        Remove-Item Env:PYTHONPATH -ErrorAction SilentlyContinue
        & $Executable @Arguments
        if ($LASTEXITCODE -ne 0) { throw "$Label failed with exit code $LASTEXITCODE" }
    }
    finally { if ($null -eq $PriorPythonPath) { Remove-Item Env:PYTHONPATH -ErrorAction SilentlyContinue } else { $env:PYTHONPATH = $PriorPythonPath } }
}

if ((git -C $Repository status --porcelain --untracked-files=all)) {
    throw 'Candidate validation requires a clean Git working tree.'
}
$Head = (git -C $Repository rev-parse HEAD).Trim()
if ([string]::IsNullOrWhiteSpace($Head)) { throw 'Could not resolve source commit.' }
foreach ($Relative in @('build', 'quillan.egg-info')) {
    $Candidate = Join-Path $Repository $Relative
    if (Test-Path -LiteralPath $Candidate) { throw "Remove generated build residue before validation: $Relative" }
}
if (Test-Path -LiteralPath $ArtifactOut) {
    $Existing = Get-Item -LiteralPath $ArtifactOut -Force
    if ($Existing.LinkType -or -not $Existing.PSIsContainer) { throw 'Artifact destination is not an ordinary directory.' }
    if (Get-ChildItem -LiteralPath $ArtifactOut -Force | Select-Object -First 1) { throw 'Artifact output must be empty.' }
}

Invoke-Required 'Authenticate released Core 0.6.5' $PythonExe @(
    (Join-Path $PSScriptRoot 'verify_core_wheel.py'), $CoreWheel,
    '--core-version', '0.6.5'
)

try {
    New-Item -ItemType Directory -Path $Artifacts, $Outside -Force | Out-Null
    if (-not $SkipRepositoryDevelopmentChecks) {
        Invoke-Required 'Repository development checks (run once)' 'powershell' @(
            '-NoProfile', '-ExecutionPolicy', 'Bypass',
            '-File', (Join-Path $Repository 'run_tests.ps1'), '-Python', $PythonExe
        )
    } else { Write-Host 'Repository checks reused from passing CI; full pytest not repeated.' }

    Push-Location $Repository
    try {
        Invoke-Required 'Build exact release wheel and sdist' $PythonExe @(
            '-m', 'build', '--wheel', '--sdist', '--outdir', $Artifacts
        )
    }
    finally { Pop-Location }
    $Wheel = Join-Path $Artifacts $WheelName
    $Sdist = Join-Path $Artifacts $SdistName
    if (-not (Test-Path -LiteralPath $Wheel -PathType Leaf) -or
        -not (Test-Path -LiteralPath $Sdist -PathType Leaf)) { throw 'Exact release artifacts missing.' }
    Invoke-Required 'Twine distribution check' $PythonExe @('-m', 'twine', 'check', $Wheel, $Sdist)
    Invoke-Required 'Inspect exact artifacts' $PythonExe @(
        (Join-Path $PSScriptRoot 'inspect_release_artifacts.py'), $Wheel, $Sdist
    )

    Invoke-Required 'Create isolated environment' $PythonExe @('-m', 'venv', $Environment)
    Push-Location $Outside
    try {
        Invoke-Required 'Install exact Core 0.6.5' $InstalledPython @('-m', 'pip', 'install', $CoreWheel)
        Invoke-Required 'Verify installed Core provenance' $InstalledPython @(
            (Join-Path $PSScriptRoot 'verify_core_wheel.py'), $CoreWheel,
            '--core-version', '0.6.5', '--verify-installed'
        )
        Invoke-Required 'Install exact Quillan 0.10.6' $InstalledPython @('-m', 'pip', 'install', $Wheel)
        Invoke-Required 'Dependency integrity' $InstalledPython @('-m', 'pip', 'check')
        Invoke-Required 'Installed reader declaration' $InstalledPython @(
            (Join-Path $PSScriptRoot 'verify_installed_issue421_reader_contract.py'),
            '--fixture', (Join-Path $Repository 'tests\fixtures\publication\quillan_academic_result_manifest_v1.json'),
            '--repository', $Repository
        )
        Invoke-Required 'Installed publication and application workflow' $InstalledPython @(
            (Join-Path $PSScriptRoot 'run_installed_acceptance.py'),
            '--work', $Work, '--repository', $Repository,
            '--full-workflow', '--expected-core-version', '0.6.5'
        )
        Invoke-Required 'Installed publication producer acceptance' $InstalledPython @(
            (Join-Path $PSScriptRoot 'verify_installed_producer_acceptance.py'),
            '--workspace', (Join-Path $Work 'workflow-workspace'),
            '--repository', $Repository, '--version', '0.10.6',
            '--expected-core-version', '0.6.5'
        )
        Invoke-Required 'Installed Issue #419 scan recovery' $InstalledPython @(
            (Join-Path $PSScriptRoot 'verify_installed_issue419_recovery.py'),
            '--workspace', $RecoveryWork, '--repository', $Repository,
            '--expected-quillan-version', '0.10.6',
            '--expected-core-version', '0.6.5'
        )
    }
    finally { Pop-Location }

    Invoke-Required 'Persist exact tested artifacts' $PythonExe @(
        (Join-Path $PSScriptRoot 'persist_release_artifacts.py'),
        '--repository', $Repository, '--output-directory', $ArtifactOut,
        '--wheel', $Wheel, '--sdist', $Sdist
    )
    Write-Host "Source commit: $Head"
    Get-FileHash -Algorithm SHA256 -LiteralPath $Wheel, $Sdist | Format-Table -AutoSize
    Write-Host 'Quillan 0.10.6 Core 0.6.5 qualification: PASS'
    Write-Host 'Release authorization: NOT GRANTED (owner must authorize tag and GitHub release)'
}
finally {
    foreach ($Relative in @('build', 'quillan.egg-info')) {
        $Candidate = Join-Path $Repository $Relative
        if (Test-Path -LiteralPath $Candidate) {
            $Item = Get-Item -LiteralPath $Candidate -Force
            if ($Item.LinkType -or -not $Item.PSIsContainer -or $Item.FullName -ne $Candidate) {
                throw "Unsafe generated path; refusing deletion: $Candidate"
            }
            Remove-Item -LiteralPath $Candidate -Recurse -Force
        }
    }
    if (Test-Path -LiteralPath $TempRoot) {
        $ResolvedTemp = (Resolve-Path -LiteralPath $TempRoot).Path
        $ExpectedPrefix = [System.IO.Path]::GetFullPath([System.IO.Path]::GetTempPath()).TrimEnd('\') + '\' + $Prefix
        if (-not $ResolvedTemp.StartsWith($ExpectedPrefix, [System.StringComparison]::OrdinalIgnoreCase)) {
            throw "Unexpected temporary cleanup root: $ResolvedTemp"
        }
        $Item = Get-Item -LiteralPath $ResolvedTemp -Force
        if ($Item.LinkType) { throw 'Refusing linked temporary cleanup root.' }
        Remove-Item -LiteralPath $ResolvedTemp -Recurse -Force
    }
}
