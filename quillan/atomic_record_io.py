"""Low-level revision-guarded persistence for canonical Quillan records."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
import os
from pathlib import Path
import sys
import tempfile
from typing import Literal


class AtomicRecordError(OSError):
    """A guarded canonical record operation failed before known completion."""


class AtomicRecordConcurrencyError(AtomicRecordError):
    """The target revision changed before this operation could install bytes."""


class AtomicRecordDurabilityError(AtomicRecordError):
    """An installed target may be durable and is deliberately preserved."""

    def __init__(
        self,
        message: str,
        *,
        possibly_durable_path: Path | None,
        possible_lock_path: Path | None = None,
    ) -> None:
        super().__init__(message)
        self.possibly_durable_path = possibly_durable_path
        self.possible_lock_path = possible_lock_path


@dataclass(frozen=True, slots=True)
class AtomicRecordResult:
    path: Path
    status: Literal["created", "updated", "unchanged"]


Preflight = Callable[[], None]
VerifyBytes = Callable[[bytes], None]


def create_exclusive_record(
    path: Path,
    replacement_bytes: bytes,
    *,
    preflight: Preflight,
    verify_bytes: VerifyBytes,
) -> AtomicRecordResult:
    """Install a same-directory temporary exclusively and verify exact bytes."""
    _require_arguments(path, replacement_bytes)
    preflight()
    if os.path.lexists(path):
        raise AtomicRecordConcurrencyError(f"Record already exists: {path}")
    lock_path = path.parent / f".{path.name}.create.lock"
    token = b"quillan-atomic-record-v1\0" + os.urandom(32)
    lock_owned = False
    temporary: Path | None = None
    installed = False
    outcome: Literal["created", "updated", "unchanged"] | None = None
    primary: BaseException | None = None
    try:
        try:
            with lock_path.open("xb") as lock_file:
                lock_owned = True
                lock_file.write(token)
                lock_file.flush()
                os.fsync(lock_file.fileno())
        except FileExistsError as error:
            raise AtomicRecordConcurrencyError(
                f"Record creation guard already exists: {lock_path}"
            ) from error
        preflight()
        if os.path.lexists(path):
            raise AtomicRecordConcurrencyError(f"Record was concurrently created: {path}")
        temporary = _write_temporary(path, replacement_bytes)
        preflight()
        if os.path.lexists(path):
            raise AtomicRecordConcurrencyError(f"Record was concurrently created: {path}")
        try:
            os.link(temporary, path)
        except FileExistsError as error:
            raise AtomicRecordConcurrencyError(
                f"Record was concurrently created: {path}"
            ) from error
        installed = True
        try:
            temporary.unlink()
        except OSError as error:
            raise AtomicRecordDurabilityError(
                f"Record was installed but its owned temporary could not be removed: {error}",
                possibly_durable_path=path,
            ) from error
        temporary = None
        _verify_installed(path, replacement_bytes, preflight, verify_bytes)
        outcome = "created"
        return AtomicRecordResult(path, "created")
    except Exception as error:
        primary = error
        if installed and not isinstance(error, AtomicRecordDurabilityError):
            durable = AtomicRecordDurabilityError(
                f"Record installation or verification is uncertain: {error}",
                possibly_durable_path=path,
            )
            durable.__cause__ = error
            primary = durable
            raise durable
        raise
    finally:
        active_error = primary if primary is not None else sys.exception()
        _cleanup_owned_temporary(temporary, active_error)
        if lock_owned:
            _remove_owned_lock(
                lock_path,
                token,
                target_path=path,
                operation_status=outcome if outcome is not None else (
                    "created" if installed else None
                ),
                primary=active_error,
            )


def revision_guarded_update(
    path: Path,
    expected_original_bytes: bytes,
    replacement_bytes: bytes,
    *,
    preflight: Preflight,
    verify_bytes: VerifyBytes,
    lock_purpose: str,
) -> AtomicRecordResult:
    """Update only the exact loaded revision under a same-directory guard.

    Once replacement occurs, this primitive never rolls older bytes back.  A
    failure or concurrent edit after installation is preserved and reported as
    possibly durable instead of risking another writer's data.
    """
    _require_arguments(path, replacement_bytes)
    if type(expected_original_bytes) is not bytes:
        raise TypeError("expected_original_bytes must be exact bytes.")
    if type(lock_purpose) is not str or not lock_purpose:
        raise TypeError("lock_purpose must be non-empty text.")
    preflight()
    _compare_revision(path, expected_original_bytes)
    lock_path = path.parent / f".{path.name}.{lock_purpose}.lock"
    token = b"quillan-atomic-record-v1\0" + os.urandom(32)
    lock_owned = False
    temporary: Path | None = None
    displaced: Path | None = None
    displaced_matches_expected = False
    installed = False
    outcome: Literal["created", "updated", "unchanged"] | None = None
    primary: BaseException | None = None
    try:
        try:
            with lock_path.open("xb") as lock_file:
                lock_owned = True
                lock_file.write(token)
                lock_file.flush()
                os.fsync(lock_file.fileno())
        except FileExistsError as error:
            raise AtomicRecordConcurrencyError(
                f"Record update guard already exists: {lock_path}"
            ) from error
        preflight()
        _compare_revision(path, expected_original_bytes)
        if replacement_bytes == expected_original_bytes:
            verify_bytes(expected_original_bytes)
            outcome = "unchanged"
            return AtomicRecordResult(path, "unchanged")
        temporary = _write_temporary(path, replacement_bytes)
        preflight()
        _compare_revision(path, expected_original_bytes)
        displaced = path.parent / (
            f".{path.name}.{lock_purpose}.{token.hex()}.displaced"
        )
        if os.path.lexists(displaced):
            raise AtomicRecordConcurrencyError(
                f"Displaced-revision path unexpectedly exists: {displaced}"
            )
        os.replace(path, displaced)
        displaced_actual = _read_ordinary_file(displaced)
        if displaced_actual != expected_original_bytes:
            raise AtomicRecordConcurrencyError(
                "Record changed immediately before guarded displacement."
            )
        displaced_matches_expected = True
        try:
            os.link(temporary, path)
        except FileExistsError as error:
            raise AtomicRecordConcurrencyError(
                "Record was concurrently recreated before exclusive installation."
            ) from error
        installed = True
        try:
            temporary.unlink()
        except OSError as error:
            raise AtomicRecordDurabilityError(
                f"Updated record was installed but its temporary remains: {error}",
                possibly_durable_path=path,
            ) from error
        temporary = None
        _verify_installed(path, replacement_bytes, preflight, verify_bytes)
        displaced.unlink()
        displaced = None
        outcome = "updated"
        return AtomicRecordResult(path, "updated")
    except Exception as error:
        primary = error
        if installed and not isinstance(error, AtomicRecordDurabilityError):
            durable = AtomicRecordDurabilityError(
                f"Updated record may be durable and was not rolled back: {error}",
                possibly_durable_path=path,
            )
            durable.__cause__ = error
            primary = durable
            raise durable
        raise
    finally:
        active_error = primary if primary is not None else sys.exception()
        if displaced is not None and not installed and active_error is not None:
            _restore_displaced_revision(
                displaced,
                path,
                known_original=displaced_matches_expected,
                primary=active_error,
            )
            if not os.path.lexists(displaced):
                displaced = None
        _cleanup_owned_temporary(temporary, active_error)
        if displaced is not None and installed and displaced_matches_expected:
            _cleanup_owned_temporary(displaced, active_error)
        if lock_owned:
            _remove_owned_lock(
                lock_path,
                token,
                target_path=path,
                operation_status=outcome if outcome is not None else (
                    "updated" if installed else None
                ),
                primary=active_error,
            )


def _write_temporary(path: Path, data: bytes) -> Path:
    descriptor = -1
    temporary: Path | None = None
    completed = False
    try:
        descriptor, name = tempfile.mkstemp(
            prefix=f".{path.name}.", suffix=".tmp", dir=path.parent
        )
        temporary = Path(name)
        with os.fdopen(descriptor, "wb") as file:
            descriptor = -1
            file.write(data)
            file.flush()
            os.fsync(file.fileno())
        completed = True
        return temporary
    finally:
        if not completed:
            active_error = sys.exception()
            if descriptor >= 0:
                try:
                    os.close(descriptor)
                except OSError as error:
                    if active_error is not None:
                        active_error.add_note(
                            f"Temporary descriptor cleanup also failed: {error}"
                        )
            if temporary is not None:
                try:
                    temporary.unlink(missing_ok=True)
                except OSError as error:
                    if active_error is not None:
                        active_error.add_note(
                            f"Owned temporary cleanup also failed: {error}"
                        )


def _verify_installed(
    path: Path,
    expected: bytes,
    preflight: Preflight,
    verify_bytes: VerifyBytes,
) -> None:
    preflight()
    actual = _read_ordinary_file(path)
    if actual != expected:
        raise AtomicRecordConcurrencyError(
            f"Installed record bytes changed before verification: {path}"
        )
    verify_bytes(actual)


def _compare_revision(path: Path, expected: bytes) -> None:
    actual = _read_ordinary_file(path)
    if actual != expected:
        raise AtomicRecordConcurrencyError(
            f"Record changed after its snapshot was loaded: {path}"
        )


def _read_ordinary_file(path: Path) -> bytes:
    if not os.path.lexists(path):
        raise AtomicRecordConcurrencyError(f"Record is missing: {path}")
    if _is_link_like(path) or not path.is_file():
        raise AtomicRecordConcurrencyError(
            f"Record is not an ordinary non-link file: {path}"
        )
    return path.read_bytes()


def _cleanup_owned_temporary(
    temporary: Path | None, primary: BaseException | None
) -> None:
    if temporary is None:
        return
    try:
        temporary.unlink(missing_ok=True)
    except OSError as error:
        if primary is not None:
            primary.add_note(f"Owned temporary cleanup also failed: {error}")
        else:
            raise AtomicRecordError(
                f"Could not remove owned temporary file {temporary}: {error}"
            ) from error


def _restore_displaced_revision(
    displaced: Path,
    target: Path,
    *,
    known_original: bool,
    primary: BaseException,
) -> None:
    """Restore exclusively, never replacing a concurrently recreated target."""
    try:
        if os.path.lexists(target):
            if known_original:
                displaced.unlink()
            else:
                primary.add_note(
                    f"A concurrently displaced revision was preserved at {displaced}."
                )
            return
        try:
            os.link(displaced, target)
        except FileExistsError:
            if known_original:
                displaced.unlink()
            else:
                primary.add_note(
                    f"A concurrently displaced revision was preserved at {displaced}."
                )
            return
        displaced.unlink()
    except OSError as error:
        primary.add_note(
            f"Could not conservatively restore displaced revision {displaced}: {error}"
        )


def _remove_owned_lock(
    lock_path: Path,
    token: bytes,
    *,
    target_path: Path,
    operation_status: Literal["created", "updated", "unchanged"] | None,
    primary: BaseException | None,
) -> None:
    try:
        if _is_link_like(lock_path) or not lock_path.is_file():
            raise AtomicRecordError(f"Update guard changed filesystem type: {lock_path}")
        if lock_path.read_bytes() != token:
            raise AtomicRecordError(f"Update guard ownership changed: {lock_path}")
        lock_path.unlink()
    except OSError as error:
        if primary is not None:
            primary.add_note(
                f"Owned record-guard cleanup also failed; possible stale lock "
                f"{lock_path}: {error}"
            )
        else:
            installed_path = (
                target_path if operation_status in {"created", "updated"} else None
            )
            qualifier = (
                f"The {operation_status} record remains installed and may be durable."
                if installed_path is not None
                else "No new record installation is claimed."
            )
            raise AtomicRecordDurabilityError(
                f"Could not conservatively remove record guard {lock_path}: {error}. "
                f"{qualifier}",
                possibly_durable_path=installed_path,
                possible_lock_path=lock_path,
            ) from error


def _require_arguments(path: Path, data: bytes) -> None:
    if type(path) is not type(Path()) or not path.is_absolute():
        raise TypeError("path must be an absolute Path.")
    if type(data) is not bytes:
        raise TypeError("replacement_bytes must be exact bytes.")


def _is_link_like(path: Path) -> bool:
    is_junction = getattr(path, "is_junction", None)
    return path.is_symlink() or bool(is_junction is not None and is_junction())


__all__: list[str] = []
