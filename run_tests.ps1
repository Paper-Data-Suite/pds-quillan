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

Invoke-Check "Running pytest..." { python -m pytest --basetemp .\.pytest-tmp }
Invoke-Check "Running Ruff..." { python -m ruff check . }
Invoke-Check "Running mypy..." { python -m mypy . }
Invoke-Check "Checking diff whitespace..." { git diff --check }

Write-Host "All checks passed."
