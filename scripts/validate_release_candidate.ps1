param(
    [string]$Python = "python",
    [Parameter(Mandatory)] [string]$PdsCoreWheel,
    [Parameter(Mandatory)] [string]$ArtifactOutputDirectory
)

$ErrorActionPreference = "Stop"
$Prefix = "pds-quillan-release-"
$Repository = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$RepositoryParent = Split-Path $Repository -Parent
$OriginalLocation = (Get-Location).Path
$ResolvedPython = (Get-Command $Python -ErrorAction Stop).Source
$CoreWheel = (Resolve-Path -LiteralPath $PdsCoreWheel).Path
$TemporaryRoot = Join-Path ([System.IO.Path]::GetTempPath()) (
    "$Prefix$([guid]::NewGuid().ToString('N'))"
)
$GeneratedBuildRoots = @(
    (Join-Path $Repository 'build'),
    (Join-Path $Repository 'quillan.egg-info')
)

function Invoke-Required {
    param([string]$Label, [string]$FilePath, [string[]]$Arguments)
    Write-Host "=== $Label ==="
    $SavedPythonPath = $env:PYTHONPATH
    try {
        Remove-Item Env:PYTHONPATH -ErrorAction SilentlyContinue
        & $FilePath @Arguments
        $ExitCode = $LASTEXITCODE
    }
    finally {
        if ($null -eq $SavedPythonPath) {
            Remove-Item Env:PYTHONPATH -ErrorAction SilentlyContinue
        }
        else { $env:PYTHONPATH = $SavedPythonPath }
    }
    if ($ExitCode -ne 0) { throw "$Label failed with exit code $ExitCode" }
}

function Remove-ValidatedTemporaryRoot {
    if (-not (Test-Path -LiteralPath $TemporaryRoot)) { return }
    $Resolved = (Resolve-Path -LiteralPath $TemporaryRoot).Path.TrimEnd('\')
    $Temp = [System.IO.Path]::GetFullPath(
        [System.IO.Path]::GetTempPath()
    ).TrimEnd('\')
    $HomePath = [System.IO.Path]::GetFullPath(
        [Environment]::GetFolderPath('UserProfile')
    ).TrimEnd('\')
    $Drive = [System.IO.Path]::GetPathRoot($Resolved).TrimEnd('\')
    $Forbidden = @(
        $Repository.TrimEnd('\'), $RepositoryParent.TrimEnd('\'),
        $OriginalLocation.TrimEnd('\'), $HomePath, $Drive
    )
    if (-not $Resolved.StartsWith($Temp + '\')) {
        throw "Refusing cleanup outside OS temp: $Resolved"
    }
    if (-not (Split-Path $Resolved -Leaf).StartsWith($Prefix)) {
        throw "Refusing cleanup with unexpected prefix: $Resolved"
    }
    if ($Forbidden -contains $Resolved) { throw "Refusing protected cleanup: $Resolved" }
    $Item = Get-Item -LiteralPath $Resolved -Force
    if ($Item.LinkType) { throw "Refusing linked cleanup root: $Resolved" }
    Remove-Item -LiteralPath $Resolved -Recurse -Force
}

function Remove-ValidatedGeneratedBuildRoots {
    foreach ($Target in $GeneratedBuildRoots) {
        if (-not (Test-Path -LiteralPath $Target)) { continue }
        $Item = Get-Item -LiteralPath $Target -Force
        if ($Item.FullName -ne $Target -or $Item.LinkType) {
            throw "Refusing unsafe generated-build cleanup: $($Item.FullName)"
        }
        Remove-Item -LiteralPath $Target -Recurse -Force
    }
}

if (-not (Test-Path -LiteralPath $CoreWheel -PathType Leaf) -or
    [System.IO.Path]::GetExtension($CoreWheel) -ne '.whl') {
    throw "PDS Core wheel must be an existing wheel file."
}
$CoreVerifier = Join-Path $PSScriptRoot 'verify_core_wheel.py'
$ArtifactPersister = Join-Path $PSScriptRoot 'persist_release_artifacts.py'
Invoke-Required "Authenticate official Core wheel" $ResolvedPython @(
    $CoreVerifier, $CoreWheel
)
foreach ($Target in $GeneratedBuildRoots) {
    if (Test-Path -LiteralPath $Target) {
        throw "Refusing to overwrite pre-existing generated-build path: $Target"
    }
}

try {
    New-Item -ItemType Directory -Path $TemporaryRoot | Out-Null
    $ArtifactRoot = Join-Path $TemporaryRoot "artifacts"
    New-Item -ItemType Directory -Path $ArtifactRoot | Out-Null
    Push-Location $Repository
    try {
        Invoke-Required "Source pytest" $ResolvedPython @('-m', 'pytest', '--basetemp', (Join-Path $TemporaryRoot 'pytest'), '-ra')
        Invoke-Required "Ruff" $ResolvedPython @('-m', 'ruff', 'check', '.')
        Invoke-Required "mypy" $ResolvedPython @('-m', 'mypy', '.', '--no-incremental')
        Invoke-Required "Documentation" $ResolvedPython @('scripts\check_documentation.py')
        Invoke-Required "Diff whitespace" 'git' @('-c', 'core.safecrlf=false', 'diff', '--check')
        Invoke-Required "Build wheel and sdist" $ResolvedPython @('-m', 'build', '--wheel', '--sdist', '--outdir', $ArtifactRoot)
        Invoke-Required "Twine" $ResolvedPython @('-m', 'twine', 'check', (Join-Path $ArtifactRoot '*'))
    }
    finally { Pop-Location }

    $Wheel = Join-Path $ArtifactRoot 'quillan-0.8.9-py3-none-any.whl'
    $Sdist = Join-Path $ArtifactRoot 'quillan-0.8.9.tar.gz'
    Invoke-Required "Artifact inspection" $ResolvedPython @((Join-Path $PSScriptRoot 'inspect_release_artifacts.py'), $Wheel, $Sdist)

    foreach ($Mode in @('wheel', 'sdist')) {
        $ModeRoot = Join-Path $TemporaryRoot $Mode
        $Environment = Join-Path $ModeRoot 'venv'
        $Work = Join-Path $ModeRoot 'outside-source'
        New-Item -ItemType Directory -Path $ModeRoot | Out-Null
        New-Item -ItemType Directory -Path $Work | Out-Null
        Invoke-Required "Create $Mode environment" $ResolvedPython @('-m', 'venv', $Environment)
        $EnvironmentPython = Join-Path $Environment 'Scripts\python.exe'
        Invoke-Required "Install Core into $Mode environment" $EnvironmentPython @('-m', 'pip', 'install', $CoreWheel)
        Invoke-Required "Verify installed Core identity ($Mode)" $EnvironmentPython @(
            $CoreVerifier, $CoreWheel, '--verify-installed'
        )
        $Artifact = if ($Mode -eq 'wheel') { $Wheel } else { $Sdist }
        Invoke-Required "Install Quillan $Mode artifact" $EnvironmentPython @('-m', 'pip', 'install', $Artifact)
        Invoke-Required "pip check ($Mode)" $EnvironmentPython @('-m', 'pip', 'check')
        $AcceptanceArguments = @(
            (Join-Path $PSScriptRoot 'run_installed_acceptance.py'),
            '--work', (Join-Path $ModeRoot 'acceptance'),
            '--repository', $Repository
        )
        if ($Mode -eq 'wheel') { $AcceptanceArguments += '--full-workflow' }
        Invoke-Required "Installed acceptance ($Mode)" $EnvironmentPython $AcceptanceArguments
    }
    Invoke-Required "Persist exact tested artifacts" $ResolvedPython @(
        $ArtifactPersister,
        '--repository', $Repository,
        '--output-directory', $ArtifactOutputDirectory,
        '--wheel', $Wheel,
        '--sdist', $Sdist
    )
    Get-FileHash -Algorithm SHA256 -LiteralPath $CoreWheel, $Wheel, $Sdist | Format-Table -AutoSize
    Write-Host "Automated release-candidate validation: PASS"
    Write-Host "Physical acceptance: PENDING OWNER"
    Write-Host "Release authorization: NOT GRANTED"
}
finally {
    Set-Location $OriginalLocation
    Remove-ValidatedGeneratedBuildRoots
    Remove-ValidatedTemporaryRoot
}
