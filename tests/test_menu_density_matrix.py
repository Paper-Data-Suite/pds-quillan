"""Authoritative registry for the real menu-density acceptance workflows."""

from __future__ import annotations


MENU_DENSITY_ACCEPTANCE_MATRIX = {
    "assignment creation": "tests/test_assignment_workflows.py::test_assignment_creation_density_uses_real_workflow",
    "assignment validation": "tests/test_assignment_workflows.py::test_assignment_validation_density_uses_real_workflow",
    "printable-response generation": "tests/test_printable_response_workflows.py::test_printable_response_density_uses_real_workflow",
    "complete scan intake": "tests/test_menu_scan_intake.py::test_complete_scan_intake_density_uses_real_workflow",
    "partial scan intake": "tests/test_menu_scan_intake.py::test_partial_scan_intake_density_uses_real_workflow",
    "Core scan review": "tests/test_menu_scan_review_resolution.py::test_menu_resolves_one_scan_review_item",
    "route selection/correction": "tests/test_menu_scan_review_resolution.py::test_route_correction_density_uses_real_workflow",
    "post-dispatch review": "tests/test_menu_scan_review_resolution.py::test_post_dispatch_density_recorder_captures_focused_segments_and_redraw",
    "successful retry": "tests/test_menu_scan_review_resolution.py::test_successful_retry_density_uses_real_workflow",
    "assignment dashboard": "tests/test_menu_export_actions.py::test_assignment_review_actions_menu_includes_export_choices",
    "full diagnostic dashboard": "tests/test_menu_export_actions.py::test_assignment_review_dashboard_hides_unused_duplicate_files",
    "student selection": "tests/test_menu_review_student_work.py::test_review_workflow_selects_context_and_shows_read_only_summary",
    "plain-paper creation": "tests/test_menu_review_student_work.py::test_review_menu_creates_plain_paper_submission_and_shows_review_actions",
    "evidence opening": "tests/test_menu_review_student_work.py::test_review_menu_open_submission_uses_existing_safe_opening",
    "page selection and page management": "tests/test_menu_review_student_work.py::test_review_menu_excludes_submission_page_without_touching_review_record",
    "minimum requirements": "tests/test_menu_review_entry_actions.py::test_review_menu_records_minimum_requirement_check",
    "review units": "tests/test_menu_review_student_work.py::test_review_menu_defines_review_units",
    "observations": "tests/test_menu_review_student_work.py::test_review_menu_records_applicable_focus_standard_observation",
    "ratings": "tests/test_menu_review_student_work.py::test_review_menu_records_and_completes_overall_focus_standard_rating",
    "feedback composition": "tests/test_menu_review_student_work.py::test_review_menu_adds_custom_focus_standard_feedback_comment",
    "teacher notes": "tests/test_menu_review_student_work.py::test_review_menu_adds_teacher_note_to_review_record",
    "workflow-state changes": "tests/test_menu_review_student_work.py::test_review_menu_updates_review_workflow_state",
    "feedback export": "tests/test_menu_export_actions.py::test_menu_export_student_feedback_creates_feedback_file",
    "assignment-report export": "tests/test_menu_export_actions.py::test_menu_export_class_summary_creates_summary_file",
    "help": "tests/test_menu_help.py::test_help_density_recorder_captures_focus_and_parent_redraw",
}

REQUIRED_MENU_DENSITY_WORKFLOWS = frozenset(MENU_DENSITY_ACCEPTANCE_MATRIX)
