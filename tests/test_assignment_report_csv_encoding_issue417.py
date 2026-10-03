"""Issue #417 Slice 1 regression tests for assignment-report CSV encoding."""

from __future__ import annotations

import codecs
import csv
from pathlib import Path

from pds_core.standards import (
    StandardDefinition,
    StandardsLibrary,
    StandardsProfile,
    write_workspace_standards_library,
)

from quillan.class_summary_export import export_class_review_summary
from quillan.report_csv import REPORT_CSV_ENCODING
from quillan.standards_summary_export import export_standards_summary
from quillan.student_performance_summary_export import (
    export_student_performance_summary,
)
from tests.review_test_support import ASSIGNMENT_ID, CLASS_ID
from tests.test_class_summary_export import (
    STANDARD_A,
    STANDARD_B,
    _write_assignment,
)

EXPECTED_STANDARD_HEADER = (
    "W.NW.11-12.3.D — Narrative Writing - Precise and Sensory Language"
)
SECOND_STANDARD_NAME = "Author’s Craft — Structure"


def _write_unicode_roster(workspace: Path) -> None:
    path = workspace / "classes" / CLASS_ID / "roster.csv"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "class_id,student_id,last_name,first_name,period\n"
        f"{CLASS_ID},00100,García,Zoë,3\n",
        encoding="utf-8",
    )


def _write_unicode_standards_library(workspace: Path) -> None:
    write_workspace_standards_library(
        workspace,
        StandardsLibrary(
            standards=(
                StandardDefinition(
                    standard_id=STANDARD_A,
                    code="W.NW.11-12.3.D",
                    source="Synthetic NJSLS-ELA",
                    short_name="Narrative Writing - Precise and Sensory Language",
                    description="Use precise words and sensory language.",
                    available_modules=("quillan",),
                ),
                StandardDefinition(
                    standard_id=STANDARD_B,
                    code="RL.TS.11-12.4",
                    source="Synthetic NJSLS-ELA",
                    short_name=SECOND_STANDARD_NAME,
                    description="Analyze structure and authorial choices.",
                    available_modules=("quillan",),
                ),
            ),
            profiles=(
                StandardsProfile(
                    profile_id="synthetic_profile",
                    standards=(STANDARD_A, STANDARD_B),
                ),
            ),
        ),
    )


def _assert_spreadsheet_utf8(path: Path) -> str:
    payload = path.read_bytes()
    assert payload.startswith(codecs.BOM_UTF8)
    assert payload.count(codecs.BOM_UTF8) == 1

    decoded = payload.decode(REPORT_CSV_ENCODING)
    assert not decoded.startswith("\ufeff")
    assert "â€”" not in decoded
    assert "â€™" not in decoded
    return decoded


def test_assignment_report_csvs_are_bom_aware_utf8_and_round_trip_unicode(
    tmp_path: Path,
) -> None:
    _write_assignment(tmp_path)
    _write_unicode_roster(tmp_path)
    _write_unicode_standards_library(tmp_path)

    student_report = export_student_performance_summary(
        tmp_path,
        CLASS_ID,
        ASSIGNMENT_ID,
    ).summary_path
    class_report = export_class_review_summary(
        tmp_path,
        CLASS_ID,
        ASSIGNMENT_ID,
    ).summary_path
    standards_report = export_standards_summary(
        tmp_path,
        CLASS_ID,
        ASSIGNMENT_ID,
    ).summary_path

    student_text = _assert_spreadsheet_utf8(student_report)
    class_text = _assert_spreadsheet_utf8(class_report)
    standards_text = _assert_spreadsheet_utf8(standards_report)

    assert EXPECTED_STANDARD_HEADER in student_text
    assert "García" in student_text
    assert "Zoë" in student_text
    assert "García" in class_text
    assert "Zoë" in class_text
    assert SECOND_STANDARD_NAME in standards_text

    with student_report.open(
        "r",
        encoding=REPORT_CSV_ENCODING,
        newline="",
    ) as file:
        reader = csv.DictReader(file)
        assert reader.fieldnames is not None
        assert reader.fieldnames[0] == "student_id"
        assert EXPECTED_STANDARD_HEADER in reader.fieldnames
        rows = list(reader)
    assert rows[0]["student_display_name"] == "Zoë García"

    with class_report.open(
        "r",
        encoding=REPORT_CSV_ENCODING,
        newline="",
    ) as file:
        reader = csv.DictReader(file)
        assert reader.fieldnames is not None
        assert reader.fieldnames[0] == "class_id"

    with standards_report.open(
        "r",
        encoding=REPORT_CSV_ENCODING,
        newline="",
    ) as file:
        reader = csv.DictReader(file)
        assert reader.fieldnames is not None
        assert reader.fieldnames[0] == "class_id"
        rows = list(reader)
    by_standard = {row["standard_id"]: row for row in rows}
    assert (
        by_standard[STANDARD_A]["standard_display_name"]
        == "Narrative Writing - Precise and Sensory Language"
    )
    assert by_standard[STANDARD_B]["standard_display_name"] == SECOND_STANDARD_NAME

    export_student_performance_summary(
        tmp_path,
        CLASS_ID,
        ASSIGNMENT_ID,
        overwrite=True,
    )
    export_class_review_summary(
        tmp_path,
        CLASS_ID,
        ASSIGNMENT_ID,
        overwrite=True,
    )
    export_standards_summary(
        tmp_path,
        CLASS_ID,
        ASSIGNMENT_ID,
        overwrite=True,
    )

    _assert_spreadsheet_utf8(student_report)
    _assert_spreadsheet_utf8(class_report)
    _assert_spreadsheet_utf8(standards_report)
