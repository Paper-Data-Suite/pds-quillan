"""Focused tests for the direct already-decoded scan routing command."""

from __future__ import annotations

import csv
import json
from pathlib import Path

import pytest
from pds_core.scan_failure_metadata import validate_routing_failure_metadata

from quillan.cli import main
import quillan.cli_app.handlers.routing as cli_routing
from quillan.evidence_filing import EvidenceFilingError
from quillan.routing_review import RoutingReviewError

CLASS_ID = "english12_p3_synthetic"
ASSIGNMENT_ID = "essay_01_synthetic"
STUDENT_ID = "00107"
VALID_PAYLOAD = (
    "PDS1|module=quillan|class=english12_p3_synthetic|"
    "aid=essay_01_synthetic|sid=00107|page=2|doc=response"
)


@pytest.fixture
def workspace(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    class_dir = tmp_path / "classes" / CLASS_ID
    assignment_dir = class_dir / "assignments" / ASSIGNMENT_ID
    assignment_dir.mkdir(parents=True)

    with (class_dir / "roster.csv").open(
        "w",
        encoding="utf-8",
        newline="",
    ) as roster_file:
        writer = csv.DictWriter(
            roster_file,
            fieldnames=(
                "class_id",
                "student_id",
                "last_name",
                "first_name",
                "period",
            ),
        )
        writer.writeheader()
        writer.writerow(
            {
                "class_id": CLASS_ID,
                "student_id": STUDENT_ID,
                "last_name": "Rivera",
                "first_name": "Avery",
                "period": "3",
            }
        )

    assignment = {
        "schema_version": "2",
        "module": "quillan",
        "record_type": "assignment",
        "assignment_id": ASSIGNMENT_ID,
        "title": "Synthetic Essay",
        "class_ids": [CLASS_ID],
        "writing_type": "argument",
        "student_prompt": "Write a synthetic argument.",
        "standards_profile_id": "synthetic_profile",
        "focus_standard_ids": ["njsls-ela:W.1"],
        "review_unit": {
            "type": "paragraph",
            "singular_label": "paragraph",
            "plural_label": "paragraphs",
        },
        "rating_scale": {
            "scale_id": "standards_2_level",
            "levels": [
                {
                    "value": 1,
                    "label": "Developing",
                    "description": "Limited evidence.",
                }
            ],
        },
        "basic_requirements": {"paragraphs_min": 1},
        "minimum_requirement_policy": {
            "allow_return_without_full_review": True,
        },
    }
    (assignment_dir / "assignment.json").write_text(
        json.dumps(assignment),
        encoding="utf-8",
    )
    monkeypatch.setattr(cli_routing, "resolve_workspace_root", lambda: tmp_path)
    return tmp_path


@pytest.fixture
def source_file(tmp_path: Path) -> Path:
    source = tmp_path / "teacher-scan.pdf"
    source.write_bytes(b"%PDF-1.4\nsynthetic response scan\n%%EOF\n")
    return source


def _review_metadata(workspace: Path) -> dict[str, object]:
    records = list((workspace / "scans" / "review").glob("*.json"))
    assert len(records) == 1
    loaded = json.loads(records[0].read_text(encoding="utf-8"))
    assert isinstance(loaded, dict)
    validate_routing_failure_metadata(loaded)
    return loaded


def test_route_scan_successfully_files_retained_and_routed_evidence(
    workspace: Path,
    source_file: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    original_bytes = source_file.read_bytes()

    result = main(
        ["route-scan", str(source_file), "--payload", VALID_PAYLOAD]
    )

    output = capsys.readouterr().out
    retained_files = list((workspace / "scans" / "source").rglob("*.pdf"))
    routed_path = (
        workspace
        / "classes"
        / CLASS_ID
        / "assignments"
        / ASSIGNMENT_ID
        / "scans"
        / "response_00107_pg_002.pdf"
    )

    assert result == 0
    assert len(retained_files) == 1
    assert retained_files[0].read_bytes() == original_bytes
    assert routed_path.read_bytes() == original_bytes
    assert source_file.read_bytes() == original_bytes
    assert not (workspace / "scans" / "review").exists()
    assert not list(workspace.rglob("submissions"))
    assert "Routed Quillan response page." in output
    assert "Routed evidence: classes/" in output
    assert "Duplicate: no" in output
    assert str(workspace) not in output


def test_route_scan_preserves_duplicate_routed_evidence(
    workspace: Path,
    source_file: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    assert main(["route-scan", str(source_file), "--payload", VALID_PAYLOAD]) == 0
    capsys.readouterr()

    assert main(["route-scan", str(source_file), "--payload", VALID_PAYLOAD]) == 0

    output = capsys.readouterr().out
    duplicate = (
        workspace
        / "classes"
        / CLASS_ID
        / "assignments"
        / ASSIGNMENT_ID
        / "scans"
        / "response_00107_pg_002__dup_001.pdf"
    )
    assert duplicate.is_file()
    assert "Duplicate: yes (__dup_001)" in output


def test_route_scan_preserves_route_planning_failure(
    workspace: Path,
    source_file: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    payload = VALID_PAYLOAD.replace(CLASS_ID, "unknown_class")

    result = main(["route-scan", str(source_file), "--payload", payload])

    output = capsys.readouterr().out
    metadata = _review_metadata(workspace)
    assert result == 0
    assert metadata["failure_category"] == "class_unknown"
    assert metadata["detected_payload"] == payload
    module_details = metadata["module_details"]
    assert isinstance(module_details, dict)
    assert module_details["failure_origin"] == "route_planning"
    assert module_details["reason"] == "class_unknown"
    assert not list(workspace.rglob("response_*.pdf"))
    assert not list(workspace.rglob("submissions"))
    assert "preserved for review" in output
    assert "Category: class_unknown" in output


def test_route_scan_preserves_payload_parse_failure(
    workspace: Path,
    source_file: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    malformed_payload = "not-a-pds1-payload"

    result = main(
        ["route-scan", str(source_file), "--payload", malformed_payload]
    )

    output = capsys.readouterr().out
    metadata = _review_metadata(workspace)
    assert result == 0
    assert metadata["failure_category"] == "payload_invalid"
    assert metadata["detected_payload"] == malformed_payload
    assert metadata["module"] is None
    assert metadata["payload_page_number"] is None
    assert metadata["class_id"] is None
    assert metadata["assignment_id"] is None
    assert metadata["student_id"] is None
    module_details = metadata["module_details"]
    assert isinstance(module_details, dict)
    assert module_details["failure_origin"] == "payload_parse"
    assert not list(workspace.rglob("response_*.pdf"))
    assert not list(workspace.rglob("submissions"))
    assert "preserved for review" in output


def test_route_scan_missing_source_returns_one_without_review_record(
    workspace: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    missing_source = workspace / "missing.pdf"

    result = main(
        ["route-scan", str(missing_source), "--payload", "malformed"]
    )

    output = capsys.readouterr().out
    assert result == 1
    assert "source file" in output
    assert "existing regular file" in output
    assert not (workspace / "scans" / "review").exists()
    assert not (workspace / "scans" / "source").exists()
    assert not list(workspace.rglob("response_*.pdf"))
    assert not list(workspace.rglob("submissions"))


def test_route_scan_directory_source_returns_one_without_review_record(
    workspace: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    result = main(
        ["route-scan", str(workspace), "--payload", "malformed"]
    )

    output = capsys.readouterr().out
    assert result == 1
    assert "--payload route-scan mode requires a source file" in output
    assert "not a folder" in output
    assert not (workspace / "scans" / "review").exists()
    assert not (workspace / "scans" / "source").exists()
    assert not list(workspace.rglob("response_*.pdf"))
    assert not list(workspace.rglob("submissions"))


@pytest.mark.parametrize(
    ("payload", "expected_category"),
    [
        (
            VALID_PAYLOAD.replace("module=quillan", "module=scoreform"),
            "module_unsupported",
        ),
        (VALID_PAYLOAD.replace("doc=response", "doc=cover"), "payload_invalid"),
        (VALID_PAYLOAD.replace("|doc=response", ""), "payload_invalid"),
    ],
)
def test_route_scan_preserves_wrong_module_or_document_type(
    workspace: Path,
    source_file: Path,
    payload: str,
    expected_category: str,
) -> None:
    assert main(["route-scan", str(source_file), "--payload", payload]) == 0

    metadata = _review_metadata(workspace)
    assert metadata["failure_category"] == expected_category
    assert metadata["detected_payload"] == payload


def test_route_scan_preserves_evidence_filing_error(
    workspace: Path,
    source_file: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fail_filing(*_args: object, **_kwargs: object) -> None:
        raise EvidenceFilingError("Synthetic disk write failure.")

    monkeypatch.setattr(
        cli_routing,
        "file_routed_response_evidence",
        fail_filing,
    )

    result = main(
        ["route-scan", str(source_file), "--payload", VALID_PAYLOAD]
    )

    output = capsys.readouterr().out
    metadata = _review_metadata(workspace)
    assert result == 0
    assert metadata["failure_category"] == "evidence_write_failed"
    assert metadata["module"] == "quillan"
    assert metadata["class_id"] == CLASS_ID
    assert metadata["assignment_id"] == ASSIGNMENT_ID
    assert metadata["student_id"] == STUDENT_ID
    assert metadata["payload_page_number"] == 2
    module_details = metadata["module_details"]
    assert isinstance(module_details, dict)
    assert module_details["failure_origin"] == "evidence_filing"
    assert "could not be filed; preserved for review" in output


def test_route_scan_returns_one_when_failure_cannot_be_preserved(
    workspace: Path,
    source_file: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fail_preservation(*_args: object, **_kwargs: object) -> None:
        raise RoutingReviewError("Synthetic review write failure.")

    monkeypatch.setattr(
        cli_routing,
        "preserve_routing_failure_for_review",
        fail_preservation,
    )

    result = main(
        ["route-scan", str(source_file), "--payload", "malformed"]
    )

    output = capsys.readouterr().out
    assert result == 1
    assert "could not be preserved for review" in output
    assert "Synthetic review write failure" in output


def test_route_scan_help_documents_safe_exit_codes(
    capsys: pytest.CaptureFixture[str],
) -> None:
    with pytest.raises(SystemExit) as error:
        main(["route-scan", "--help"])

    output = capsys.readouterr().out
    assert error.value.code == 0
    assert "already-decoded Quillan PDS1 payload" in output
    assert "Exit 0" in output
    assert "exit 1" in output


def test_route_scan_does_not_create_downstream_or_intake_outputs(
    workspace: Path,
    source_file: Path,
) -> None:
    assert main(["route-scan", str(source_file), "--payload", VALID_PAYLOAD]) == 0

    prohibited_names = {
        "submission.json",
        "requirements.json",
        "tags.json",
        "scores.json",
        "feedback.md",
    }
    assert not [
        path for path in workspace.rglob("*") if path.name in prohibited_names
    ]
    assert not (workspace / "reports").exists()
    assert not (workspace / "scans_inbox").exists()
