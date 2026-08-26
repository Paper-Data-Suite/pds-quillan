param(
    [string]$Python = "python",
    [Parameter(Mandatory)] [string]$PdsCore062Wheel,
    [Parameter(Mandatory)] [string]$PdsCore063Wheel,
    [Parameter(Mandatory)] [string]$ArtifactOutputDirectory,
    [switch]$SkipRepositoryDevelopmentChecks
)

$ErrorActionPreference = "Stop"
$Prefix = "pds-quillan-v0100-candidate-"
$Repository = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$RepositoryParent = Split-Path $Repository -Parent
$OriginalLocation = (Get-Location).Path
$ResolvedPython = (Get-Command $Python -ErrorAction Stop).Source
$Core062Wheel = (Resolve-Path -LiteralPath $PdsCore062Wheel).Path
$Core063Wheel = (Resolve-Path -LiteralPath $PdsCore063Wheel).Path
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
    if ($Forbidden -contains $Resolved) {
        throw "Refusing protected cleanup: $Resolved"
    }
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

$CoreVerifier = Join-Path $PSScriptRoot 'verify_core_wheel.py'
$ArtifactPersister = Join-Path $PSScriptRoot 'persist_release_artifacts.py'
$ArtifactInspector = Join-Path $PSScriptRoot 'inspect_release_artifacts.py'
$InstalledAcceptance = Join-Path $PSScriptRoot 'run_installed_acceptance.py'
$ProducerAcceptance = Join-Path $PSScriptRoot 'verify_installed_producer_acceptance.py'
$OperationsAcceptance = Join-Path $PSScriptRoot 'verify_installed_operations_acceptance.py'
$ClassSetAcceptance = Join-Path $PSScriptRoot 'verify_installed_class_set_acceptance.py'
$ReleaseEdgeAcceptance = Join-Path $PSScriptRoot 'verify_installed_release_edges.py'

Invoke-Required "Authenticate official Core 0.6.2 wheel" $ResolvedPython @(
    $CoreVerifier, $Core062Wheel, '--core-version', '0.6.2'
)
Invoke-Required "Authenticate official Core 0.6.3 wheel" $ResolvedPython @(
    $CoreVerifier, $Core063Wheel, '--core-version', '0.6.3'
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
        if ($SkipRepositoryDevelopmentChecks) {
            Write-Host "=== Repository development checks ==="
            Write-Host (
                "REUSED: repository development checks already passed in this qualification cycle; " +
                "full pytest is not being repeated."
            )
        }
        else {
            Invoke-Required "Repository development checks" 'powershell' @(
                '-NoProfile', '-ExecutionPolicy', 'Bypass',
                '-File', (Join-Path $Repository 'run_tests.ps1'),
                '-Python', $ResolvedPython
            )
        }
        Invoke-Required "compileall" $ResolvedPython @(
            '-m', 'compileall', '-q', 'quillan', 'tests'
        )
        Invoke-Required "Build one wheel and sdist" $ResolvedPython @(
            '-m', 'build', '--wheel', '--sdist', '--outdir', $ArtifactRoot
        )
        Invoke-Required "Twine" $ResolvedPython @(
            '-m', 'twine', 'check', (Join-Path $ArtifactRoot '*')
        )
    }
    finally { Pop-Location }

    $Wheel = Join-Path $ArtifactRoot 'quillan-0.10.0-py3-none-any.whl'
    $Sdist = Join-Path $ArtifactRoot 'quillan-0.10.0.tar.gz'
    Invoke-Required "Artifact inspection" $ResolvedPython @(
        $ArtifactInspector, $Wheel, $Sdist
    )

    $Endpoints = @(
        @{ Version = '0.6.2'; Wheel = $Core062Wheel },
        @{ Version = '0.6.3'; Wheel = $Core063Wheel }
    )

    foreach ($Endpoint in $Endpoints) {
        $CoreVersion = $Endpoint.Version
        $CoreWheel = $Endpoint.Wheel
        $ModeRoot = Join-Path $TemporaryRoot ("core-" + $CoreVersion.Replace('.', ''))
        $Environment = Join-Path $ModeRoot 'venv'
        $Work = Join-Path $ModeRoot 'outside-source'
        $Acceptance = Join-Path $ModeRoot 'acceptance'
        $OperationsWorkspace = Join-Path $ModeRoot 'operations-workspace'
        New-Item -ItemType Directory -Path $ModeRoot | Out-Null
        New-Item -ItemType Directory -Path $Work | Out-Null
        New-Item -ItemType Directory -Path $OperationsWorkspace | Out-Null

        Invoke-Required "Create Core $CoreVersion environment" $ResolvedPython @(
            '-m', 'venv', $Environment
        )
        $EnvironmentPython = Join-Path $Environment 'Scripts\python.exe'
        Invoke-Required "Install Core $CoreVersion" $EnvironmentPython @(
            '-m', 'pip', 'install', $CoreWheel
        )
        Invoke-Required "Verify installed Core $CoreVersion" $EnvironmentPython @(
            $CoreVerifier, $CoreWheel, '--core-version', $CoreVersion,
            '--verify-installed'
        )
        Invoke-Required "Install exact Quillan wheel for Core $CoreVersion" `
            $EnvironmentPython @('-m', 'pip', 'install', $Wheel)
        Invoke-Required "pip check Core $CoreVersion" $EnvironmentPython @(
            '-m', 'pip', 'check'
        )

        Push-Location $Work
        try {
            Invoke-Required "Installed application workflow Core $CoreVersion" `
                $EnvironmentPython @(
                    $InstalledAcceptance,
                    '--work', $Acceptance,
                    '--repository', $Repository,
                    '--full-workflow',
                    '--expected-core-version', $CoreVersion
                )
            Invoke-Required "Installed producer lifecycle Core $CoreVersion" `
                $EnvironmentPython @(
                    $ProducerAcceptance,
                    '--workspace', (Join-Path $Acceptance 'workflow-workspace'),
                    '--repository', $Repository,
                    '--version', '0.10.0',
                    '--expected-core-version', $CoreVersion
                )
            Invoke-Required "Installed module operations Core $CoreVersion" `
                $EnvironmentPython @(
                    $OperationsAcceptance,
                    '--workspace', $OperationsWorkspace,
                    '--repository', $Repository,
                    '--expected-core-version', $CoreVersion
                )
            Invoke-Required "Installed class-set acceptance Core $CoreVersion" `
                $EnvironmentPython @(
                    $ClassSetAcceptance,
                    '--workspace', (Join-Path $Acceptance 'workflow-workspace'),
                    '--repository', $Repository,
                    '--expected-core-version', $CoreVersion
                )
            Invoke-Required "Installed release-edge acceptance Core $CoreVersion" `
                $EnvironmentPython @(
                    $ReleaseEdgeAcceptance,
                    '--workspace', (Join-Path $Acceptance 'workflow-workspace'),
                    '--repository', $Repository,
                    '--expected-core-version', $CoreVersion
                )
        }
        finally { Pop-Location }
    }

    $SdistRoot = Join-Path $TemporaryRoot 'sdist'
    $SdistEnvironment = Join-Path $SdistRoot 'venv'
    $SdistWork = Join-Path $SdistRoot 'outside-source'
    New-Item -ItemType Directory -Path $SdistRoot | Out-Null
    New-Item -ItemType Directory -Path $SdistWork | Out-Null
    Invoke-Required "Create sdist environment" $ResolvedPython @(
        '-m', 'venv', $SdistEnvironment
    )
    $SdistPython = Join-Path $SdistEnvironment 'Scripts\python.exe'
    Invoke-Required "Install Core 0.6.3 for sdist smoke" $SdistPython @(
        '-m', 'pip', 'install', $Core063Wheel
    )
    Invoke-Required "Install exact Quillan sdist" $SdistPython @(
        '-m', 'pip', 'install', $Sdist
    )
    Invoke-Required "pip check sdist" $SdistPython @('-m', 'pip', 'check')
    Push-Location $SdistWork
    try {
        Invoke-Required "Installed sdist smoke" $SdistPython @(
            $InstalledAcceptance,
            '--work', (Join-Path $SdistRoot 'acceptance'),
            '--repository', $Repository,
            '--expected-core-version', '0.6.3'
        )
    }
    finally { Pop-Location }

    Invoke-Required "Persist exact tested artifacts" $ResolvedPython @(
        $ArtifactPersister,
        '--repository', $Repository,
        '--output-directory', $ArtifactOutputDirectory,
        '--wheel', $Wheel,
        '--sdist', $Sdist
    )

    Get-Item -LiteralPath $Wheel, $Sdist |
        Select-Object Name, Length |
        Format-Table -AutoSize
    Get-FileHash -Algorithm SHA256 -LiteralPath `
        $Core062Wheel, $Core063Wheel, $Wheel, $Sdist |
        Format-Table -AutoSize

    Write-Host "Automated v0.10.0 candidate validation: PASS"
    Write-Host "Physical acceptance: PENDING OWNER"
    Write-Host "READY FOR #394: NO"
    Write-Host "Release authorization: NOT GRANTED"
}
finally {
    Set-Location $OriginalLocation
    Remove-ValidatedGeneratedBuildRoots
    Remove-ValidatedTemporaryRoot
}
