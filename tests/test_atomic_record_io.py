"""Fault-injection tests for guarded canonical-record lock cleanup."""

from __future__ import annotations

from pathlib import Path
from collections.abc import Callable
from typing import NoReturn

import pytest

from quillan.atomic_record_io import (
    AtomicRecordDurabilityError,
    create_exclusive_record,
    revision_guarded_update,
)


def _preflight() -> None:
    return None


def _verify(expected: bytes) -> Callable[[bytes], None]:
    def verify(actual: bytes) -> None:
        assert actual == expected

    return verify


def _fail_only_lock_unlink(
    monkeypatch: pytest.MonkeyPatch, lock_path: Path
) -> None:
    original_unlink = Path.unlink

    def unlink(path: Path, missing_ok: bool = False) -> None:
        if path == lock_path:
            raise OSError("synthetic lock unlink failure")
        original_unlink(path, missing_ok)

    monkeypatch.setattr(Path, "unlink", unlink)


def test_lock_unlink_failure_after_create_reports_durable_and_stale_paths(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    target = (tmp_path / "record.json").absolute()
    lock_path = target.parent / ".record.json.create.lock"
    _fail_only_lock_unlink(monkeypatch, lock_path)

    with pytest.raises(AtomicRecordDurabilityError) as captured:
        create_exclusive_record(
            target,
            b"created",
            preflight=_preflight,
            verify_bytes=_verify(b"created"),
        )

    assert captured.value.possibly_durable_path == target
    assert captured.value.possible_lock_path == lock_path
    assert target.read_bytes() == b"created"
    assert lock_path.is_file()


def test_lock_unlink_failure_after_update_preserves_installed_bytes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    target = (tmp_path / "record.json").absolute()
    target.write_bytes(b"original")
    lock_path = target.parent / ".record.json.update.lock"
    _fail_only_lock_unlink(monkeypatch, lock_path)

    with pytest.raises(AtomicRecordDurabilityError) as captured:
        revision_guarded_update(
            target,
            b"original",
            b"replacement",
            preflight=_preflight,
            verify_bytes=_verify(b"replacement"),
            lock_purpose="update",
        )

    assert captured.value.possibly_durable_path == target
    assert captured.value.possible_lock_path == lock_path
    assert target.read_bytes() == b"replacement"
    assert lock_path.is_file()


def test_lock_unlink_failure_after_unchanged_reports_only_stale_lock(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    target = (tmp_path / "record.json").absolute()
    target.write_bytes(b"same")
    lock_path = target.parent / ".record.json.unchanged.lock"
    _fail_only_lock_unlink(monkeypatch, lock_path)

    with pytest.raises(AtomicRecordDurabilityError) as captured:
        revision_guarded_update(
            target,
            b"same",
            b"same",
            preflight=_preflight,
            verify_bytes=_verify(b"same"),
            lock_purpose="unchanged",
        )

    assert captured.value.possibly_durable_path is None
    assert captured.value.possible_lock_path == lock_path
    assert "No new record installation is claimed" in str(captured.value)
    assert target.read_bytes() == b"same"


def test_primary_persistence_failure_keeps_primary_and_attaches_lock_diagnostic(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    target = (tmp_path / "record.json").absolute()
    lock_path = target.parent / ".record.json.create.lock"
    _fail_only_lock_unlink(monkeypatch, lock_path)

    def fail_verification(_actual: bytes) -> NoReturn:
        raise ValueError("synthetic primary verification failure")

    with pytest.raises(AtomicRecordDurabilityError) as captured:
        create_exclusive_record(
            target,
            b"installed",
            preflight=_preflight,
            verify_bytes=fail_verification,
        )

    assert isinstance(captured.value.__cause__, ValueError)
    assert "primary verification failure" in str(captured.value.__cause__)
    assert any(str(lock_path) in note for note in captured.value.__notes__)
    assert target.read_bytes() == b"installed"
    assert lock_path.is_file()


def test_changed_lock_token_is_preserved_and_reported(
    tmp_path: Path,
) -> None:
    target = (tmp_path / "record.json").absolute()
    lock_path = target.parent / ".record.json.create.lock"

    def change_token(actual: bytes) -> None:
        assert actual == b"installed"
        lock_path.write_bytes(b"another owner")

    with pytest.raises(AtomicRecordDurabilityError) as captured:
        create_exclusive_record(
            target,
            b"installed",
            preflight=_preflight,
            verify_bytes=change_token,
        )

    assert captured.value.possibly_durable_path == target
    assert captured.value.possible_lock_path == lock_path
    assert lock_path.read_bytes() == b"another owner"
    assert target.read_bytes() == b"installed"


@pytest.mark.parametrize("interrupt", [KeyboardInterrupt(), SystemExit(7), GeneratorExit()])
def test_base_exceptions_propagate_without_relabeling_and_preserve_installed_bytes(
    tmp_path: Path,
    interrupt: BaseException,
) -> None:
    target = (tmp_path / "record.json").absolute()

    def interrupt_verification(_actual: bytes) -> NoReturn:
        raise interrupt

    with pytest.raises(type(interrupt)) as captured:
        create_exclusive_record(
            target,
            b"installed",
            preflight=_preflight,
            verify_bytes=interrupt_verification,
        )

    assert captured.value is interrupt
    assert target.read_bytes() == b"installed"
    assert not list(tmp_path.glob("*.lock"))
