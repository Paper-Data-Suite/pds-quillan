"""Contract tests for exact authoritative PDS Core wheel authentication."""

from __future__ import annotations

import hashlib
import importlib.metadata as importlib_metadata
from pathlib import Path
import sys
from types import SimpleNamespace
import zipfile

import pytest

from scripts.verify_core_wheel import (
    AUTHORITATIVE_CORE_FILENAME,
    CoreWheelContract,
    CoreWheelVerificationError,
    installed_core_identity,
    verify_core_wheel,
)
import scripts.verify_core_wheel as verifier


def _wheel(
    root: Path,
    *,
    filename: str = AUTHORITATIVE_CORE_FILENAME,
    distribution: str = "pds-core",
    version: str = "0.5.0",
    include_metadata: bool = True,
) -> Path:
    path = root / filename
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("pds_core/__init__.py", "")
        if include_metadata:
            archive.writestr(
                "pds_core-0.5.0.dist-info/METADATA",
                f"Metadata-Version: 2.4\nName: {distribution}\nVersion: {version}\n",
            )
    return path


def _matching_contract(path: Path) -> CoreWheelContract:
    return CoreWheelContract(sha256=hashlib.sha256(path.read_bytes()).hexdigest())


def test_correct_metadata_and_hash_contract_is_accepted(tmp_path: Path) -> None:
    wheel = _wheel(tmp_path)
    verified = verify_core_wheel(wheel, _matching_contract(wheel))
    assert verified.filename == AUTHORITATIVE_CORE_FILENAME
    assert verified.distribution == "pds-core"
    assert verified.version == "0.5.0"


def test_wrong_filename_is_rejected(tmp_path: Path) -> None:
    wheel = _wheel(tmp_path, filename="wrong.whl")
    with pytest.raises(CoreWheelVerificationError, match="filename"):
        verify_core_wheel(wheel, _matching_contract(wheel))


@pytest.mark.parametrize(
    ("field", "value", "message"),
    (("distribution", "not-core", "distribution"), ("version", "0.5.1", "version")),
)
def test_wrong_embedded_identity_is_rejected(
    tmp_path: Path, field: str, value: str, message: str
) -> None:
    options = {field: value}
    wheel = _wheel(tmp_path, **options)  # type: ignore[arg-type]
    with pytest.raises(CoreWheelVerificationError, match=message):
        verify_core_wheel(wheel, _matching_contract(wheel))


def test_wrong_hash_is_rejected(tmp_path: Path) -> None:
    wheel = _wheel(tmp_path)
    with pytest.raises(CoreWheelVerificationError, match="SHA-256"):
        verify_core_wheel(wheel, CoreWheelContract(sha256="0" * 64))


def test_malformed_archive_is_rejected(tmp_path: Path) -> None:
    wheel = tmp_path / AUTHORITATIVE_CORE_FILENAME
    wheel.write_bytes(b"not a wheel")
    with pytest.raises(CoreWheelVerificationError, match="readable wheel archive"):
        verify_core_wheel(wheel, _matching_contract(wheel))


def test_missing_metadata_is_rejected(tmp_path: Path) -> None:
    wheel = _wheel(tmp_path, include_metadata=False)
    with pytest.raises(CoreWheelVerificationError, match="exactly one"):
        verify_core_wheel(wheel, _matching_contract(wheel))


def test_renaming_an_untrusted_wheel_does_not_authenticate_it(tmp_path: Path) -> None:
    wheel = _wheel(tmp_path, distribution="renamed-untrusted")
    with pytest.raises(CoreWheelVerificationError, match="SHA-256"):
        verify_core_wheel(wheel)


def _installed_identity(
    monkeypatch: pytest.MonkeyPatch,
    *,
    environment: Path,
    distribution_location: Path,
    import_path: Path,
    version: str = "0.5.0",
) -> None:
    import_path.parent.mkdir(parents=True, exist_ok=True)
    import_path.touch()
    distribution_location.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(sys, "prefix", str(environment))
    monkeypatch.setattr(importlib_metadata, "version", lambda _: version)
    monkeypatch.setattr(
        importlib_metadata,
        "distribution",
        lambda _: SimpleNamespace(locate_file=lambda _: distribution_location),
    )
    monkeypatch.setitem(sys.modules, "pds_core", SimpleNamespace(__file__=str(import_path)))


def test_installed_metadata_version_mismatch_is_rejected(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    environment = tmp_path / "env"
    location = environment / "Lib" / "site-packages"
    _installed_identity(
        monkeypatch,
        environment=environment,
        distribution_location=location,
        import_path=location / "pds_core" / "__init__.py",
        version="0.5.1",
    )
    with pytest.raises(CoreWheelVerificationError, match="version"):
        installed_core_identity()


def test_import_path_outside_active_environment_is_rejected(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    environment = tmp_path / "env"
    _installed_identity(
        monkeypatch,
        environment=environment,
        distribution_location=environment / "Lib" / "site-packages",
        import_path=tmp_path / "shadow" / "pds_core" / "__init__.py",
    )
    with pytest.raises(CoreWheelVerificationError, match="import path.*outside"):
        installed_core_identity()


def test_distribution_location_outside_active_environment_is_rejected(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    environment = tmp_path / "env"
    _installed_identity(
        monkeypatch,
        environment=environment,
        distribution_location=tmp_path / "external-site-packages",
        import_path=environment / "Lib" / "site-packages" / "pds_core" / "__init__.py",
    )
    with pytest.raises(CoreWheelVerificationError, match="distribution location.*outside"):
        installed_core_identity()


def test_source_shadowed_import_origin_is_rejected(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    checkout_parent = tmp_path / "Paper-Data-Suite"
    environment = checkout_parent
    location = checkout_parent / "pds-core"
    monkeypatch.setattr(
        verifier,
        "__file__",
        str(checkout_parent / "pds-quillan" / "scripts" / "verify_core_wheel.py"),
    )
    _installed_identity(
        monkeypatch,
        environment=environment,
        distribution_location=location,
        import_path=location / "pds_core" / "__init__.py",
    )
    with pytest.raises(CoreWheelVerificationError, match="source-shadowed"):
        installed_core_identity()
