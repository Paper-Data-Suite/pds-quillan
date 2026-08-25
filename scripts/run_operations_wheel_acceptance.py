"""Build and qualify the current Quillan wheel in an isolated environment."""

from __future__ import annotations

import argparse
from email.parser import BytesParser
from email.policy import default
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import venv
import zipfile


class OperationsWheelAcceptanceError(RuntimeError):
    """Raised when isolated current-wheel qualification cannot be completed."""


def _run(
    command: list[str],
    *,
    cwd: Path,
    env: dict[str, str] | None = None,
) -> None:
    environment = os.environ.copy() if env is None else dict(env)
    environment.pop("PYTHONPATH", None)
    subprocess.run(
        command,
        cwd=cwd,
        env=environment,
        check=True,
    )


def _environment_python(environment: Path) -> Path:
    if os.name == "nt":
        return environment / "Scripts" / "python.exe"
    return environment / "bin" / "python"


def _wheel_version(wheel: Path) -> str:
    with zipfile.ZipFile(wheel) as archive:
        names = [
            name
            for name in archive.namelist()
            if name.count("/") == 1 and name.endswith(".dist-info/METADATA")
        ]
        if len(names) != 1:
            raise OperationsWheelAcceptanceError(
                "built wheel must contain exactly one top-level METADATA file"
            )
        message = BytesParser(policy=default).parsebytes(archive.read(names[0]))
    if message.get("Name") != "quillan":
        raise OperationsWheelAcceptanceError("built wheel distribution is not quillan")
    version = message.get("Version")
    if not isinstance(version, str) or not version:
        raise OperationsWheelAcceptanceError("built wheel version is missing")
    return version


def _remove_generated_build_roots(repository: Path) -> None:
    for relative in (Path("build"), Path("quillan.egg-info")):
        target = repository / relative
        if target.exists():
            if target.is_symlink():
                raise OperationsWheelAcceptanceError(
                    f"refusing to clean linked generated path: {target}"
                )
            shutil.rmtree(target)


def run_acceptance(
    *,
    repository: Path,
    work: Path,
    core_wheel: Path,
    expected_core_version: str,
) -> dict[str, object]:
    repository = repository.resolve(strict=True)
    core_wheel = core_wheel.resolve(strict=True)
    work = work.resolve()

    if work.exists():
        if any(work.iterdir()):
            raise OperationsWheelAcceptanceError(
                "--work must be absent or an empty directory"
            )
    else:
        work.mkdir(parents=True)

    generated_roots = (repository / "build", repository / "quillan.egg-info")
    if any(path.exists() for path in generated_roots):
        raise OperationsWheelAcceptanceError(
            "refusing to overwrite pre-existing build or quillan.egg-info"
        )

    artifacts = work / "artifacts"
    environment = work / "venv"
    outside = work / "outside-source"
    installed_acceptance = work / "installed-acceptance"
    operations_workspace = work / "operations-workspace"
    artifacts.mkdir()
    outside.mkdir()
    operations_workspace.mkdir()

    try:
        _run(
            [
                sys.executable,
                "-m",
                "build",
                "--wheel",
                "--sdist",
                "--outdir",
                str(artifacts),
            ],
            cwd=repository,
        )

        wheels = tuple(artifacts.glob("quillan-*-py3-none-any.whl"))
        sdists = tuple(artifacts.glob("quillan-*.tar.gz"))
        if len(wheels) != 1 or len(sdists) != 1:
            raise OperationsWheelAcceptanceError(
                "build must produce exactly one Quillan wheel and one sdist"
            )
        wheel = wheels[0]
        sdist = sdists[0]
        version = _wheel_version(wheel)

        _run(
            [
                sys.executable,
                str(repository / "scripts" / "inspect_release_artifacts.py"),
                str(wheel),
                str(sdist),
            ],
            cwd=repository,
        )

        venv.EnvBuilder(with_pip=True, clear=False).create(environment)
        python = _environment_python(environment)
        if not python.is_file():
            raise OperationsWheelAcceptanceError(
                "isolated environment Python was not created"
            )

        _run(
            [str(python), "-m", "pip", "install", str(core_wheel)],
            cwd=outside,
        )
        _run(
            [
                str(python),
                str(repository / "scripts" / "verify_core_wheel.py"),
                str(core_wheel),
                "--core-version",
                expected_core_version,
                "--verify-installed",
            ],
            cwd=outside,
        )
        _run(
            [str(python), "-m", "pip", "install", str(wheel)],
            cwd=outside,
        )
        _run([str(python), "-m", "pip", "check"], cwd=outside)

        _run(
            [
                str(python),
                str(repository / "scripts" / "run_installed_acceptance.py"),
                "--work",
                str(installed_acceptance),
                "--repository",
                str(repository),
                "--full-workflow",
                "--expected-core-version",
                expected_core_version,
            ],
            cwd=outside,
        )
        workflow_workspace = installed_acceptance / "workflow-workspace"
        if not workflow_workspace.is_dir():
            raise OperationsWheelAcceptanceError(
                "installed full workflow did not create its expected workspace"
            )

        _run(
            [
                str(python),
                str(
                    repository
                    / "scripts"
                    / "verify_installed_producer_acceptance.py"
                ),
                "--workspace",
                str(workflow_workspace),
                "--repository",
                str(repository),
                "--version",
                version,
                "--expected-core-version",
                expected_core_version,
            ],
            cwd=outside,
        )

        _run(
            [
                str(python),
                str(
                    repository
                    / "scripts"
                    / "verify_installed_operations_acceptance.py"
                ),
                "--workspace",
                str(operations_workspace),
                "--repository",
                str(repository),
                "--expected-core-version",
                expected_core_version,
            ],
            cwd=outside,
        )

        return {
            "wheel": str(wheel),
            "sdist": str(sdist),
            "quillan_version": version,
            "core_version": expected_core_version,
            "isolated_environment": str(environment),
            "application_acceptance": "passed",
            "routing_publication_acceptance": "passed",
            "operations_acceptance": "passed",
        }
    finally:
        _remove_generated_build_roots(repository)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repository", required=True, type=Path)
    parser.add_argument("--work", required=True, type=Path)
    parser.add_argument("--core-wheel", required=True, type=Path)
    parser.add_argument(
        "--expected-core-version",
        required=True,
        choices=("0.6.2", "0.6.3"),
    )
    args = parser.parse_args()
    try:
        result = run_acceptance(
            repository=args.repository,
            work=args.work,
            core_wheel=args.core_wheel,
            expected_core_version=args.expected_core_version,
        )
    except (
        OperationsWheelAcceptanceError,
        OSError,
        subprocess.CalledProcessError,
    ) as error:
        parser.exit(
            1,
            f"Installed operations-wheel acceptance failed: {error}\n",
        )
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
