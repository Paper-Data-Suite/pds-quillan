"""Authenticate the exact official PDS Core 0.5.0 release wheel."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from email.parser import BytesParser
from email.policy import default
import hashlib
import importlib.metadata as metadata
import json
from pathlib import Path
import sys
from typing import Final
import zipfile


AUTHORITATIVE_CORE_FILENAME: Final = "pds_core-0.5.0-py3-none-any.whl"
AUTHORITATIVE_CORE_SHA256: Final = (
    "336676fa4b72e2b4094f654e77b5746b0d6670946cb4c5d3022c4c0be7963400"
)
AUTHORITATIVE_CORE_DISTRIBUTION: Final = "pds-core"
AUTHORITATIVE_CORE_VERSION: Final = "0.5.0"


class CoreWheelVerificationError(ValueError):
    """Raised when a supplied Core wheel is not the authoritative release asset."""


@dataclass(frozen=True, slots=True)
class CoreWheelContract:
    """Exact authenticated identity expected for one Core wheel."""

    filename: str = AUTHORITATIVE_CORE_FILENAME
    sha256: str = AUTHORITATIVE_CORE_SHA256
    distribution: str = AUTHORITATIVE_CORE_DISTRIBUTION
    version: str = AUTHORITATIVE_CORE_VERSION


@dataclass(frozen=True, slots=True)
class VerifiedCoreWheel:
    """Authenticated wheel identity suitable for validator output."""

    path: Path
    filename: str
    sha256: str
    distribution: str
    version: str
    metadata_path: str


def verify_core_wheel(
    path: str | Path, contract: CoreWheelContract = CoreWheelContract()
) -> VerifiedCoreWheel:
    """Authenticate filename, bytes, and embedded distribution metadata."""
    wheel = Path(path).resolve()
    if not wheel.is_file():
        raise CoreWheelVerificationError("Core wheel must be an existing file.")
    if wheel.name != contract.filename:
        raise CoreWheelVerificationError(
            f"Core wheel filename must be exactly {contract.filename}."
        )
    digest = hashlib.sha256(wheel.read_bytes()).hexdigest()
    if digest != contract.sha256:
        raise CoreWheelVerificationError(
            f"Core wheel SHA-256 mismatch: expected {contract.sha256}, got {digest}."
        )
    try:
        with zipfile.ZipFile(wheel) as archive:
            metadata_names = sorted(
                name
                for name in archive.namelist()
                if name.count("/") == 1 and name.endswith(".dist-info/METADATA")
            )
            if len(metadata_names) != 1:
                raise CoreWheelVerificationError(
                    "Core wheel must contain exactly one top-level dist-info/METADATA."
                )
            metadata_path = metadata_names[0]
            message = BytesParser(policy=default).parsebytes(
                archive.read(metadata_path)
            )
    except CoreWheelVerificationError:
        raise
    except (OSError, KeyError, zipfile.BadZipFile) as error:
        raise CoreWheelVerificationError(
            f"Core wheel is not a readable wheel archive: {error}"
        ) from error
    distribution = message.get("Name")
    version = message.get("Version")
    if distribution != contract.distribution:
        raise CoreWheelVerificationError(
            f"Core wheel distribution must be exactly {contract.distribution}."
        )
    if version != contract.version:
        raise CoreWheelVerificationError(
            f"Core wheel version must be exactly {contract.version}."
        )
    return VerifiedCoreWheel(
        path=wheel,
        filename=wheel.name,
        sha256=digest,
        distribution=distribution,
        version=version,
        metadata_path=metadata_path,
    )


def installed_core_identity() -> dict[str, str]:
    """Verify Core metadata and prove its import comes from this environment."""
    version = metadata.version(AUTHORITATIVE_CORE_DISTRIBUTION)
    if version != AUTHORITATIVE_CORE_VERSION:
        raise CoreWheelVerificationError(
            f"Installed pds-core version must be {AUTHORITATIVE_CORE_VERSION}, got {version}."
        )
    import pds_core

    raw_import_path = getattr(pds_core, "__file__", None)
    if not raw_import_path:
        raise CoreWheelVerificationError("Installed pds_core.__file__ is missing.")
    import_path = Path(raw_import_path).resolve()
    if not import_path.is_file():
        raise CoreWheelVerificationError(
            "Installed pds_core.__file__ must resolve to an ordinary file."
        )
    environment = Path(sys.prefix).resolve()
    distribution = metadata.distribution(AUTHORITATIVE_CORE_DISTRIBUTION)
    distribution_location = Path(str(distribution.locate_file(""))).resolve()
    if not import_path.is_relative_to(environment):
        raise CoreWheelVerificationError(
            "Installed pds_core import path is outside the active environment."
        )
    if not distribution_location.is_relative_to(environment):
        raise CoreWheelVerificationError(
            "Installed pds-core distribution location is outside the active environment."
        )
    if not import_path.is_relative_to(distribution_location):
        raise CoreWheelVerificationError(
            "Installed pds_core import is outside the pds-core distribution location."
        )
    repository = Path(__file__).resolve().parents[1]
    checkout_parent = repository.parent
    forbidden_source_packages = (
        repository / "pds_core",
        checkout_parent / "pds-core" / "pds_core",
        checkout_parent / "pds_core" / "pds_core",
    )
    if any(import_path.is_relative_to(root) for root in forbidden_source_packages):
        raise CoreWheelVerificationError(
            "Installed pds_core import is source-shadowed by Quillan or a sibling checkout."
        )

    return {
        "installed_distribution": AUTHORITATIVE_CORE_DISTRIBUTION,
        "installed_version": version,
        "installed_import_path": str(import_path),
        "installed_distribution_location": str(distribution_location),
        "installed_environment": str(environment),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("wheel", type=Path)
    parser.add_argument("--verify-installed", action="store_true")
    args = parser.parse_args()
    try:
        verified = verify_core_wheel(args.wheel)
        result = {
            "path": str(verified.path),
            "filename": verified.filename,
            "sha256": verified.sha256,
            "distribution": verified.distribution,
            "version": verified.version,
            "metadata_path": verified.metadata_path,
        }
        if args.verify_installed:
            result.update(installed_core_identity())
    except CoreWheelVerificationError as error:
        parser.exit(1, f"Core wheel verification failed: {error}\n")
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
