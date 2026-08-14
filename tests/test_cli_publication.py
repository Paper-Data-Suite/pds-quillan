"""Direct CLI tests for explicit Quillan publication lifecycle commands."""

from __future__ import annotations

import argparse
from pathlib import Path

import pytest

import quillan.cli_app.handlers.publication as handlers
from quillan.academic_result_publication import (
    publish_quillan_academic_results,
)
from quillan.cli_app.handlers.publication import (
    handle_publication_list,
    handle_publication_publish,
    handle_publication_rebuild_catalog,
    handle_publication_republish_after_withdrawal,
    handle_publication_show,
    handle_publication_status,
    handle_publication_supersede,
    handle_publication_withdraw,
)
from quillan.cli_app.parser import build_parser
from tests.review_test_support import ASSIGNMENT_ID, CLASS_ID
from tests.test_academic_result_publication import _registered_manifest


@pytest.mark.parametrize(
    ("argv", "handler"),
    [
        (
            [
                "publication",
                "status",
                "--class-id",
                "class1",
                "--assignment-id",
                "essay1",
            ],
            handle_publication_status,
        ),
        (
            [
                "publication",
                "list",
                "--class-id",
                "class1",
                "--assignment-id",
                "essay1",
            ],
            handle_publication_list,
        ),
        (
            [
                "publication",
                "show",
                "--class-id",
                "class1",
                "--assignment-id",
                "essay1",
                "--publication-id",
                "pub_0123456789abcdef0123456789abcdef",
            ],
            handle_publication_show,
        ),
        (
            [
                "publication",
                "publish",
                "--class-id",
                "class1",
                "--assignment-id",
                "essay1",
                "--revision",
                "2",
            ],
            handle_publication_publish,
        ),
        (
            [
                "publication",
                "supersede",
                "--class-id",
                "class1",
                "--assignment-id",
                "essay1",
                "--revision",
                "2",
                "--expected-current-publication-id",
                "pub_0123456789abcdef0123456789abcdef",
            ],
            handle_publication_supersede,
        ),
        (
            [
                "publication",
                "republish-after-withdrawal",
                "--class-id",
                "class1",
                "--assignment-id",
                "essay1",
                "--expected-current-publication-id",
                "pub_0123456789abcdef0123456789abcdef",
            ],
            handle_publication_republish_after_withdrawal,
        ),
        (
            [
                "publication",
                "withdraw",
                "--class-id",
                "class1",
                "--assignment-id",
                "essay1",
                "--publication-id",
                "pub_0123456789abcdef0123456789abcdef",
                "--reason",
                "operator supplied reason",
            ],
            handle_publication_withdraw,
        ),
        (
            ["publication", "rebuild-catalog"],
            handle_publication_rebuild_catalog,
        ),
    ],
)
def test_publication_parser_routes_exact_commands(
    argv: list[str],
    handler: object,
) -> None:
    args = build_parser().parse_args(argv)
    assert args.handler is handler


def test_publication_parser_requires_positive_revision() -> None:
    parser = build_parser()
    with pytest.raises(SystemExit):
        parser.parse_args(
            [
                "publication",
                "publish",
                "--class-id",
                "class1",
                "--assignment-id",
                "essay1",
                "--revision",
                "0",
            ]
        )


def test_publication_status_is_privacy_minimized(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    _, manifest = _registered_manifest(tmp_path)
    published = publish_quillan_academic_results(
        tmp_path,
        CLASS_ID,
        ASSIGNMENT_ID,
        manifest_revision=manifest.revision,
    )
    monkeypatch.setattr(handlers, "resolve_workspace_root", lambda: tmp_path)

    code = handlers.handle_publication_status(
        argparse.Namespace(class_id=CLASS_ID, assignment_id=ASSIGNMENT_ID)
    )

    assert code == 0
    output = capsys.readouterr().out
    assert published.publication.publication_id in output
    assert "producer head revision: 1" in output
    assert "student" not in output.lower()
    assert "rating" not in output.lower()
    assert "rationale" not in output.lower()


def test_publication_withdraw_does_not_echo_reason(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    _, manifest = _registered_manifest(tmp_path)
    published = publish_quillan_academic_results(
        tmp_path,
        CLASS_ID,
        ASSIGNMENT_ID,
        manifest_revision=manifest.revision,
    )
    monkeypatch.setattr(handlers, "resolve_workspace_root", lambda: tmp_path)
    secret_reason = "SECRET-WITHDRAWAL-REASON"

    code = handlers.handle_publication_withdraw(
        argparse.Namespace(
            class_id=CLASS_ID,
            assignment_id=ASSIGNMENT_ID,
            publication_id=published.publication.publication_id,
            reason=secret_reason,
        )
    )

    captured = capsys.readouterr()
    assert code == 0
    assert secret_reason not in captured.out
    assert secret_reason not in captured.err
    assert "withdrawn: yes" in captured.out
    assert "catalog reconciliation: verified" in captured.out


def test_publication_error_does_not_print_underlying_exception_text(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setattr(handlers, "resolve_workspace_root", lambda: Path("workspace"))

    def fail(*_args: object, **_kwargs: object) -> None:
        from quillan.academic_result_publication import (
            QuillanAcademicResultPublicationIntegrityError,
        )

        raise QuillanAcademicResultPublicationIntegrityError(
            r"C:\private\student-data\SECRET.json"
        )

    monkeypatch.setattr(handlers, "load_quillan_publication_series_status", fail)
    code = handlers.handle_publication_status(
        argparse.Namespace(class_id="class1", assignment_id="essay1")
    )

    captured = capsys.readouterr()
    assert code == 1
    assert "SECRET.json" not in captured.err
    assert "private" not in captured.err
    assert "failed integrity checks" in captured.err
