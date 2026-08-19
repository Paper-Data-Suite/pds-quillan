"""Execute and capture the reproducible Quillan issue #379 workflow audit."""

from __future__ import annotations

from datetime import datetime, timezone
from importlib import metadata
import os
from pathlib import Path
import platform
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

REPORT_PATH = ROOT / "docs" / "v0.10.0_teacher_workflow_audit.md"


def _run(command: list[str], *, env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        cwd=ROOT,
        env=env,
        check=False,
        capture_output=True,
        text=True,
    )


def _git_sha() -> str:
    result = _run(["git", "rev-parse", "HEAD"])
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or "could not read Git HEAD")
    return result.stdout.strip()


def _pds_core_version() -> str:
    try:
        return metadata.version("pds-core")
    except metadata.PackageNotFoundError as error:
        raise RuntimeError("installed pds-core package version could not be determined") from error


def main() -> int:
    from quillan._version import __version__ as quillan_version
    from tests.teacher_workflow_audit_reporting import (
        AuditProvenance,
        parse_metric_rows,
        render_teacher_workflow_audit_report,
    )

    env = os.environ.copy()
    env["QUILLAN_TEACHER_WORKFLOW_AUDIT"] = "1"
    command = [
        sys.executable,
        "-m",
        "pytest",
        "-m",
        "menu_density_workflow or menu_density_contract",
        "-q",
        "-s",
    ]
    result = _run(command, env=env)
    if result.stdout:
        print(result.stdout, end="")
    if result.stderr:
        print(result.stderr, end="", file=sys.stderr)
    if result.returncode != 0:
        return result.returncode

    rows = parse_metric_rows(result.stdout)
    provenance = AuditProvenance(
        git_sha=_git_sha(),
        quillan_version=quillan_version,
        python_version=platform.python_version(),
        pds_core_version=_pds_core_version(),
        operating_system=f"{platform.system()} {platform.release()}",
        generated_at_utc=datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
    )
    report = render_teacher_workflow_audit_report(rows, provenance)
    REPORT_PATH.write_text(report, encoding="utf-8")
    print(f"Teacher-workflow audit report written: {REPORT_PATH.relative_to(ROOT).as_posix()}")
    print(f"Audited Git SHA: {provenance.git_sha}")
    print(f"Quillan version: {provenance.quillan_version}")
    print(f"Python version: {provenance.python_version}")
    print(f"pds-core version: {provenance.pds_core_version}")
    print(f"Operating system: {provenance.operating_system}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
