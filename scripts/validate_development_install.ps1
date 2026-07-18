param(
    [string]$Python = "python",
    [string]$PdsCoreWheel
)

$ErrorActionPreference = "Stop"
$ScriptPrefix = "pds-quillan-install-"
$Failures = [System.Collections.Generic.List[string]]::new()

function Invoke-Required {
    param(
        [Parameter(Mandatory)] [string]$Description,
        [Parameter(Mandatory)] [string]$FilePath,
        [Parameter(Mandatory)] [string[]]$ArgumentList
    )

    Write-Host $Description
    & $FilePath @ArgumentList
    if ($LASTEXITCODE -ne 0) {
        throw "$Description failed with exit code $LASTEXITCODE."
    }
}

function Invoke-Captured {
    param(
        [Parameter(Mandatory)] [string]$Description,
        [Parameter(Mandatory)] [string]$FilePath,
        [Parameter(Mandatory)] [string[]]$ArgumentList,
        [Parameter(Mandatory)] [string]$CaptureDirectory
    )

    $SafeName = $Description -replace '[^A-Za-z0-9]+', '-'
    $StdoutPath = Join-Path $CaptureDirectory "$SafeName.stdout.txt"
    $StderrPath = Join-Path $CaptureDirectory "$SafeName.stderr.txt"
    $PreviousErrorActionPreference = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    try {
        & $FilePath @ArgumentList 1> $StdoutPath 2> $StderrPath
        $ExitCode = $LASTEXITCODE
    }
    finally {
        $ErrorActionPreference = $PreviousErrorActionPreference
    }
    $Stdout = Get-Content -LiteralPath $StdoutPath -Raw -ErrorAction SilentlyContinue
    $Stderr = Get-Content -LiteralPath $StderrPath -Raw -ErrorAction SilentlyContinue
    Write-Host "$Description exit code: $ExitCode"
    Write-Host "$Description stdout:"
    Write-Host $Stdout
    Write-Host "$Description stderr:"
    Write-Host $Stderr
    return [pscustomobject]@{
        ExitCode = $ExitCode
        Stdout = $Stdout
        Stderr = $Stderr
    }
}

function Add-Failure {
    param([Parameter(Mandatory)] [string]$Message)
    $Failures.Add($Message)
    Write-Host "FAIL: $Message"
}

function Assert-WorkspaceAbsent {
    param(
        [Parameter(Mandatory)] [string]$Operation,
        [Parameter(Mandatory)] [string]$WorkspaceRoot
    )
    if (Test-Path -LiteralPath $WorkspaceRoot) {
        Add-Failure "$Operation created the configured workspace: $WorkspaceRoot"
    }
    else {
        Write-Host "$Operation workspace side-effect check: PASS"
    }
}

function Remove-ValidatedTemporaryRoot {
    param(
        [Parameter(Mandatory)] [string]$TemporaryRoot,
        [Parameter(Mandatory)] [string]$Repository,
        [Parameter(Mandatory)] [string]$RepositoryParent,
        [Parameter(Mandatory)] [string]$OriginalLocation
    )

    if (-not (Test-Path -LiteralPath $TemporaryRoot)) {
        return
    }
    $ResolvedRoot = (Resolve-Path -LiteralPath $TemporaryRoot).Path.TrimEnd('\')
    $ResolvedTemp = [System.IO.Path]::GetFullPath(
        [System.IO.Path]::GetTempPath()
    ).TrimEnd('\')
    $Leaf = Split-Path $ResolvedRoot -Leaf
    $HomePath = [System.IO.Path]::GetFullPath(
        [Environment]::GetFolderPath('UserProfile')
    ).TrimEnd('\')
    $DriveRoot = [System.IO.Path]::GetPathRoot($ResolvedRoot).TrimEnd('\')
    $Forbidden = @(
        $Repository.TrimEnd('\'),
        $RepositoryParent.TrimEnd('\'),
        $HomePath,
        $DriveRoot,
        $OriginalLocation.TrimEnd('\')
    )
    if (-not $ResolvedRoot.StartsWith($ResolvedTemp + '\')) {
        throw "Refusing to delete temporary root outside OS temp: $ResolvedRoot"
    }
    if (-not $Leaf.StartsWith($ScriptPrefix)) {
        throw "Refusing to delete temporary root with unexpected name: $ResolvedRoot"
    }
    if ($Forbidden -contains $ResolvedRoot) {
        throw "Refusing to delete protected path: $ResolvedRoot"
    }
    Remove-Item -LiteralPath $ResolvedRoot -Recurse -Force
    Write-Host "Temporary root cleanup: PASS ($ResolvedRoot)"
}

$Repository = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$RepositoryParent = (Split-Path $Repository -Parent)
$OriginalLocation = (Get-Location).Path
$TemporaryRoot = Join-Path ([System.IO.Path]::GetTempPath()) (
    "$ScriptPrefix$([guid]::NewGuid().ToString('N'))"
)
if (Test-Path -LiteralPath $TemporaryRoot) {
    throw "Refusing to reuse temporary root: $TemporaryRoot"
}

$WheelInput = if ($PSBoundParameters.ContainsKey('PdsCoreWheel')) {
    $PdsCoreWheel
}
elseif ($env:PDS_CORE_WHEEL) {
    $env:PDS_CORE_WHEEL
}
else {
    $null
}
$ResolvedCoreWheel = $null
if ($WheelInput) {
    $ResolvedCoreWheel = (Resolve-Path -LiteralPath $WheelInput).Path
    if (-not (Test-Path -LiteralPath $ResolvedCoreWheel -PathType Leaf)) {
        throw "PDS Core wheel is not a regular file: $ResolvedCoreWheel"
    }
    if ([System.IO.Path]::GetExtension($ResolvedCoreWheel) -ne '.whl') {
        throw "PDS Core wheel must have a .whl extension: $ResolvedCoreWheel"
    }
    Write-Host "Core installation source: supplied wheel $ResolvedCoreWheel"
}
else {
    Write-Host "Core installation source: normal pip dependency resolution"
}

$HadWorkspaceRoot = Test-Path Env:PDS_WORKSPACE_ROOT
$PreviousWorkspaceRoot = $env:PDS_WORKSPACE_ROOT
$PreviousPath = $env:PATH

try {
    New-Item -ItemType Directory -Path $TemporaryRoot -ErrorAction Stop | Out-Null
    foreach ($Mode in @('editable', 'noneditable')) {
        Write-Host "=== Validating $Mode installation ==="
        $ModeRoot = Join-Path $TemporaryRoot $Mode
        $EnvironmentRoot = Join-Path $ModeRoot 'venv'
        $WorkingDirectory = Join-Path $ModeRoot 'work'
        $CaptureDirectory = Join-Path $ModeRoot 'captures'
        $WorkspaceRoot = Join-Path $ModeRoot 'workspace-must-not-exist'
        New-Item -ItemType Directory -Path $WorkingDirectory | Out-Null
        New-Item -ItemType Directory -Path $CaptureDirectory | Out-Null
        Invoke-Required "Creating $Mode virtual environment" $Python @(
            '-m', 'venv', $EnvironmentRoot
        )

        $EnvironmentPython = Join-Path $EnvironmentRoot 'Scripts\python.exe'
        $EnvironmentScripts = Join-Path $EnvironmentRoot 'Scripts'
        $QuillanCommand = Join-Path $EnvironmentScripts 'quillan.exe'
        if ($ResolvedCoreWheel) {
            Invoke-Required "Installing supplied Core wheel into $Mode environment" `
                $EnvironmentPython @('-m', 'pip', 'install', '--quiet', $ResolvedCoreWheel)
        }

        $InstallTarget = "$Repository[dev]"
        $InstallArguments = @('-m', 'pip', 'install', '--quiet')
        if ($Mode -eq 'editable') {
            $InstallArguments += '-e'
        }
        $InstallArguments += $InstallTarget
        Push-Location $WorkingDirectory
        try {
            & $EnvironmentPython @InstallArguments
            $InstallExitCode = $LASTEXITCODE
        }
        finally {
            Pop-Location
        }
        if ($InstallExitCode -ne 0) {
            if (-not $ResolvedCoreWheel) {
                throw (
                    "Quillan requires pds-core>=0.5,<0.6, but no compatible " +
                    "distribution was resolved. Supply a verified Core wheel with " +
                    "-PdsCoreWheel or PDS_CORE_WHEEL. This script will not fall " +
                    "back to a neighboring source checkout."
                )
            }
            throw "Installing Quillan in $Mode mode failed with exit code $InstallExitCode."
        }

        Invoke-Required "Running pip check in $Mode environment" `
            $EnvironmentPython @('-m', 'pip', 'check')

        $MetadataCheck = @'
import importlib.metadata as metadata
import json
import pathlib
import sys
from packaging.requirements import Requirement
from packaging.specifiers import SpecifierSet
from packaging.version import Version

quillan = metadata.distribution('quillan')
requirements = [Requirement(value) for value in quillan.requires or []]
core = [value for value in requirements if value.name == 'pds-core']
assert len(core) == 1, core
assert core[0].url is None, core[0]
assert {str(value) for value in core[0].specifier} == {'>=0.5', '<0.6'}, core[0]
installed_core = metadata.distribution('pds-core')
assert Version(installed_core.version) in SpecifierSet('>=0.5,<0.6'), installed_core.version
scripts = [entry for entry in quillan.entry_points if entry.group == 'console_scripts']
assert any(entry.name == 'quillan' and entry.value == 'quillan.cli:main' for entry in scripts), scripts
print(json.dumps({
    'quillan_version': quillan.version,
    'quillan_location': str(pathlib.Path(quillan.locate_file('')).resolve()),
    'core_requirement': str(core[0]),
    'core_version': installed_core.version,
    'core_location': str(pathlib.Path(installed_core.locate_file('')).resolve()),
    'console_script': 'quillan=quillan.cli:main',
}, indent=2, sort_keys=True))
'@
        $MetadataResult = Invoke-Captured "$Mode distribution metadata" `
            $EnvironmentPython @('-c', $MetadataCheck) $CaptureDirectory
        if ($MetadataResult.ExitCode -ne 0) {
            Add-Failure "$Mode distribution metadata validation failed"
        }

        $env:PDS_WORKSPACE_ROOT = $WorkspaceRoot
        if (Test-Path -LiteralPath $WorkspaceRoot) {
            throw "Configured test workspace unexpectedly exists: $WorkspaceRoot"
        }
        $CommonImportCheck = @'
import json
import pathlib
import sys
import pds_core
import quillan
import quillan.pds_contract

def locations(module):
    if getattr(module, '__file__', None):
        return [str(pathlib.Path(module.__file__).resolve())]
    return [str(pathlib.Path(value).resolve()) for value in module.__path__]

environment = pathlib.Path(sys.argv[1]).resolve()
repository = pathlib.Path(sys.argv[2]).resolve()
mode = sys.argv[3]
paths = {
    'pds_core': locations(pds_core),
    'quillan': locations(quillan),
    'quillan.pds_contract': locations(quillan.pds_contract),
}
assert all(pathlib.Path(value).is_relative_to(environment) for value in paths['pds_core']), paths
if mode == 'noneditable':
    for name in ('quillan', 'quillan.pds_contract'):
        assert all(not pathlib.Path(value).is_relative_to(repository) for value in paths[name]), paths
print(json.dumps(paths, indent=2, sort_keys=True))
'@
        Push-Location $WorkingDirectory
        try {
            $ContractResult = Invoke-Captured "$Mode contract import" `
                $EnvironmentPython @(
                    '-c', $CommonImportCheck, $EnvironmentRoot, $Repository, $Mode
                ) $CaptureDirectory
        }
        finally {
            Pop-Location
        }
        if ($ContractResult.ExitCode -ne 0) {
            Add-Failure "$Mode contract import failed"
        }
        Assert-WorkspaceAbsent "$Mode contract import" $WorkspaceRoot

        $CliImportCheck = @'
import json
import pathlib
import sys
import quillan.cli

path = pathlib.Path(quillan.cli.__file__).resolve()
repository = pathlib.Path(sys.argv[1]).resolve()
if sys.argv[2] == 'noneditable':
    assert not path.is_relative_to(repository), path
print(json.dumps({'quillan.cli': str(path)}, indent=2))
'@
        Push-Location $WorkingDirectory
        try {
            $CliImportResult = Invoke-Captured "$Mode CLI import" `
                $EnvironmentPython @('-c', $CliImportCheck, $Repository, $Mode) `
                $CaptureDirectory
        }
        finally {
            Pop-Location
        }
        if ($CliImportResult.ExitCode -ne 0) {
            Add-Failure "$Mode CLI import failed"
        }
        Assert-WorkspaceAbsent "$Mode CLI import" $WorkspaceRoot

        if (-not (Test-Path -LiteralPath $QuillanCommand -PathType Leaf)) {
            Add-Failure "$Mode absolute console command is missing: $QuillanCommand"
        }
        else {
            Push-Location $WorkingDirectory
            try {
                $AbsoluteHelp = Invoke-Captured "$Mode absolute CLI help" `
                    $QuillanCommand @('--help') $CaptureDirectory
            }
            finally {
                Pop-Location
            }
            if (
                $AbsoluteHelp.ExitCode -ne 0 -or
                [string]::IsNullOrWhiteSpace($AbsoluteHelp.Stdout) -or
                $AbsoluteHelp.Stdout -match 'Traceback|unhandled exception' -or
                $AbsoluteHelp.Stderr -match 'Traceback|unhandled exception'
            ) {
                Add-Failure "$Mode absolute CLI help failed"
            }
        }
        Assert-WorkspaceAbsent "$Mode absolute CLI help" $WorkspaceRoot

        $env:PATH = "$EnvironmentScripts;$PreviousPath"
        Push-Location $WorkingDirectory
        try {
            $PathHelp = Invoke-Captured "$Mode PATH CLI help" `
                'quillan' @('--help') $CaptureDirectory
        }
        finally {
            Pop-Location
            $env:PATH = $PreviousPath
        }
        if (
            $PathHelp.ExitCode -ne 0 -or
            [string]::IsNullOrWhiteSpace($PathHelp.Stdout) -or
            $PathHelp.Stdout -match 'Traceback|unhandled exception' -or
            $PathHelp.Stderr -match 'Traceback|unhandled exception'
        ) {
            Add-Failure "$Mode PATH CLI help failed"
        }
        Assert-WorkspaceAbsent "$Mode PATH CLI help" $WorkspaceRoot
    }

    if ($Failures.Count -gt 0) {
        throw "Installation validation failed: $($Failures -join '; ')"
    }
    Write-Host "Editable and noneditable installation validation passed."
}
finally {
    Set-Location $OriginalLocation
    $env:PATH = $PreviousPath
    if ($HadWorkspaceRoot) {
        $env:PDS_WORKSPACE_ROOT = $PreviousWorkspaceRoot
    }
    else {
        Remove-Item Env:PDS_WORKSPACE_ROOT -ErrorAction SilentlyContinue
    }
    Remove-ValidatedTemporaryRoot $TemporaryRoot $Repository `
        $RepositoryParent $OriginalLocation
}
