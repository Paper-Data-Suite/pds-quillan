param([string]$Python = "python")

$ErrorActionPreference = "Stop"
$Repository = (Resolve-Path -LiteralPath $PSScriptRoot).Path
$BaseTemp = Join-Path $Repository ".pytest-tmp"
$ResolvedPython = (Get-Command $Python -ErrorAction Stop).Source

function Invoke-Check {
    param([string]$Label, [scriptblock]$Command)
    Write-Host "=== $Label ==="
    & $Command
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
}

function Remove-ValidatedPytestTemp {
    if (-not (Test-Path -LiteralPath $BaseTemp)) { return }
    $Item = Get-Item -LiteralPath $BaseTemp -Force
    $Expected = [System.IO.Path]::GetFullPath(
        (Join-Path $Repository ".pytest-tmp")
    ).TrimEnd('\')
    if ($Item.FullName.TrimEnd('\') -ne $Expected) {
        throw "Refusing to clean unexpected pytest path: $($Item.FullName)"
    }
    if ($Item.LinkType) {
        throw "Refusing to recursively clean linked pytest path: $($Item.FullName)"
    }
    Remove-Item -LiteralPath $Item.FullName -Recurse -Force
}

Write-Host "Python executable: $ResolvedPython"
& $ResolvedPython --version
& $ResolvedPython -m pip --version
foreach ($Tool in @('pytest', 'ruff', 'mypy', 'build', 'twine', 'packaging')) {
    & $ResolvedPython -c (
        "import importlib.metadata as m; print('$Tool ' + m.version('$Tool'))"
    )
}

try {
    Invoke-Check "Dependency check" { & $ResolvedPython -m pip check }
    Invoke-Check "Full pytest" {
        & $ResolvedPython -m pytest --basetemp $BaseTemp -ra
    }
    Invoke-Check "Ruff" { & $ResolvedPython -m ruff check . }
    Invoke-Check "mypy (no incremental cache)" {
        & $ResolvedPython -m mypy . --no-incremental
    }
    Invoke-Check "Documentation integrity" {
        & $ResolvedPython scripts\check_documentation.py
    }
    Invoke-Check "Diff whitespace" {
        $PreviousPreference = $ErrorActionPreference
        $ErrorActionPreference = "Continue"
        try { git -c core.safecrlf=false diff --check }
        finally { $ErrorActionPreference = $PreviousPreference }
    }
}
finally {
    Remove-ValidatedPytestTemp
}

Write-Host "All development checks passed."
