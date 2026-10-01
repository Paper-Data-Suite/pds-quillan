"""Issue #416 Slice 1: persisted Core retained-provenance compatibility."""

from __future__ import annotations

from datetime import date, datetime
import hashlib
import json
from pathlib import Path
from typing import Any, cast

import pytest

from quillan.retained_source_provenance import (
    validate_core_retention_event_consistency,
    validate_serialized_core_retention_event_consistency,
)

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests" / "fixtures" / "issue416" / "retained_source_provenance.json"


def _fixture() -> dict[str, Any]:
    value = json.loads(FIXTURE.read_text(encoding="utf-8"))
    assert isinstance(value, dict)
    return cast(dict[str, Any], value)


def _variant(name: str) -> dict[str, str]:
    value = _fixture()[name]
    assert isinstance(value, dict)
    return cast(dict[str, str], value)


def _timestamp() -> datetime:
    return datetime.fromisoformat(cast(str, _fixture()["intake_timestamp"]))


def _date() -> date:
    return date.fromisoformat(cast(str, _fixture()["intake_date"]))


def _physical_arguments(workspace: Path, variant: str) -> dict[str, Any]:
    data = _fixture()
    identity = _variant(variant)
    retained = workspace / Path(identity["retained_source_relative_path"])
    retained.parent.mkdir(parents=True, exist_ok=True)
    retained.write_bytes(cast(str, data["content_text"]).encode("utf-8"))
    return {
        "source_scan_id": identity["source_scan_id"],
        "source_filename": data["source_filename"],
        "source_sha256": data["source_sha256"],
        "retained_source_path": retained,
        "retained_source_relative_path": identity["retained_source_relative_path"],
        "intake_timestamp": _timestamp(),
        "intake_date": _date(),
        "workspace_root": workspace,
    }


def _serialized_arguments(variant: str) -> dict[str, object]:
    data = _fixture()
    identity = _variant(variant)
    return {
        "source_scan_id": identity["source_scan_id"],
        "source_filename": data["source_filename"],
        "source_sha256": data["source_sha256"],
        "retained_source_relative_path": identity["retained_source_relative_path"],
        "intake_timestamp": data["intake_timestamp"],
        "intake_date": data["intake_date"],
    }


def test_issue416_fixture_preserves_legacy_and_bounded_core_identities() -> None:
    data = _fixture()
    legacy = _variant("legacy_v063")
    bounded = _variant("bounded_v064")

    content = cast(str, data["content_text"]).encode("utf-8")
    assert hashlib.sha256(content).hexdigest() == data["source_sha256"]
    assert legacy["retained_filename"] != bounded["retained_filename"]
    assert len(legacy["retained_filename"]) > len(bounded["retained_filename"])
    assert legacy["source_scan_id"] == (
        f"scan_{Path(legacy['retained_filename']).stem}"
    )
    assert bounded["source_scan_id"] == (
        f"scan_{Path(bounded['retained_filename']).stem}"
    )


@pytest.mark.parametrize("variant", ["legacy_v063", "bounded_v064"])
def test_persisted_core_identity_validates_without_writer_reconstruction(
    tmp_path: Path,
    variant: str,
) -> None:
    arguments = _physical_arguments(tmp_path, variant)
    expected = _variant(variant)

    identity = validate_core_retention_event_consistency(**arguments)

    assert identity.retained_filename == expected["retained_filename"]
    assert (
        identity.retained_relative_path.as_posix()
        == expected["retained_source_relative_path"]
    )
    assert identity.source_scan_id == expected["source_scan_id"]


@pytest.mark.parametrize("variant", ["legacy_v063", "bounded_v064"])
def test_serialized_persisted_core_identity_accepts_both_forms(variant: str) -> None:
    expected = _variant(variant)

    identity = validate_serialized_core_retention_event_consistency(
        **_serialized_arguments(variant)
    )

    assert identity.retained_filename == expected["retained_filename"]
    assert identity.source_scan_id == expected["source_scan_id"]


def test_source_filename_is_authoritative_provenance_not_writer_input(
    tmp_path: Path,
) -> None:
    arguments = _physical_arguments(tmp_path, "legacy_v063")
    arguments["source_filename"] = "historical_teacher_selected_name.pdf"

    identity = validate_core_retention_event_consistency(**arguments)

    assert identity.retained_filename == _variant("legacy_v063")["retained_filename"]


@pytest.mark.parametrize(
    ("field", "replacement", "message"),
    [
        ("source_scan_id", "scan_arbitrary_safe", "source_scan_id contradicts"),
        ("source_sha256", "b" * 64, "digest contradicts"),
        (
            "intake_timestamp",
            datetime.fromisoformat("2026-09-30T03:18:39.064717+00:00"),
            "timestamp contradicts",
        ),
        ("source_filename", "different.png", "extensions disagree"),
        ("intake_date", date(2026, 10, 1), "date bucket contradicts"),
    ],
)
def test_durable_cross_field_contradictions_remain_rejected(
    tmp_path: Path,
    field: str,
    replacement: object,
    message: str,
) -> None:
    arguments = _physical_arguments(tmp_path, "legacy_v063")
    arguments[field] = replacement

    with pytest.raises(ValueError, match=message):
        validate_core_retention_event_consistency(**arguments)


def test_absolute_and_relative_retained_paths_must_still_agree(tmp_path: Path) -> None:
    arguments = _physical_arguments(tmp_path, "legacy_v063")
    other = tmp_path / "elsewhere" / _variant("legacy_v063")["retained_filename"]
    other.parent.mkdir()
    other.write_bytes(b"sentinel")
    arguments["retained_source_path"] = other

    with pytest.raises(ValueError, match="absolute and relative paths disagree"):
        validate_core_retention_event_consistency(**arguments)


def test_validator_source_does_not_call_current_core_writer() -> None:
    source = (
        ROOT / "quillan" / "retained_source_provenance.py"
    ).read_text(encoding="utf-8")

    assert "build_retained_source_filename" not in source
    assert "retained_source_scan_path" in source
