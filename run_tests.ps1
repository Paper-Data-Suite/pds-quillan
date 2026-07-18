param(
    [string]$Python = "python"
)

$ErrorActionPreference = "Stop"

function Invoke-Check {
    param(
        [Parameter(Mandatory)]
        [string]$Label,

        [Parameter(Mandatory)]
        [scriptblock]$Command
    )

    Write-Host $Label
    & $Command

    if ($LASTEXITCODE -ne 0) {
        exit $LASTEXITCODE
    }
}

$ResolvedPython = (Get-Command $Python -ErrorAction Stop).Source
Write-Host "Using Python: $ResolvedPython"

Invoke-Check "Installing Quillan with development extras..." {
    & $ResolvedPython -m pip install -e ".[dev]"
}
Invoke-Check "Checking installed dependencies..." { & $ResolvedPython -m pip check }
Invoke-Check "Verifying installed imports..." {
    & $ResolvedPython -c "import pds_core; import quillan.pds_contract; import quillan.cli"
}
Invoke-Check "Running pytest..." {
    & $ResolvedPython -m pytest --basetemp .\.pytest-tmp
}
Invoke-Check "Running Ruff..." { & $ResolvedPython -m ruff check . }
Invoke-Check "Running mypy..." { & $ResolvedPython -m mypy . }
Invoke-Check "Checking diff whitespace..." { git diff --check }

Write-Host "All checks passed."
