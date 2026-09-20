"""Read-only planning and atomic assembly of current feedback PDFs."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timezone
from hashlib import sha256
from io import BytesIO
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import tempfile
from typing import Any, Final, Literal, cast
import unicodedata
from zipfile import ZIP_DEFLATED, ZipFile

from pypdf import PdfReader, PdfWriter

from quillan._path_safety import is_link_like
from quillan.feedback_export import feedback_pdf_export_path
from quillan.review_work_queue import (
    AssignmentReviewWorkQueue,
    ReviewWorkQueueError,
    ReviewWorkQueueItem,
    build_assignment_review_work_queue,
)
from quillan.student_review_status import (
    StudentReviewStatusError,
    build_student_review_status,
    student_review_status_to_dict,
)
from quillan.work_paths import quillan_work_paths

AssemblyScope = Literal["whole_class", "selected"]
AssemblyOutput = Literal["print", "bundle", "both"]
AssemblyStatus = Literal[
    "current",
    "missing",
    "stale",
    "metadata_invalid",
    "identity_mismatch",
    "unavailable",
    "source_pdf_unreadable",
]

_OUTPUTS: Final = frozenset({"print", "bundle", "both"})
_BATCH_ID = re.compile(r"^[0-9]{8}T[0-9]{6}Z$")
_ILLEGAL_FILENAME = re.compile(r'[<>:"/\\|?*\x00-\x1f]')


class BatchFeedbackAssemblyError(ValueError):
    """Raised when a feedback batch cannot be safely planned or assembled."""


@dataclass(frozen=True, slots=True)
class FeedbackAssemblyStudentPlan:
    """Bounded current-artifact state for one roster student."""

    student_id: str
    display_name: str
    status: AssemblyStatus
    reason_code: str
    source_relative_path: str
    review_updated_at: str | None
    source_review_updated_at: str | None
    source_size: int | None
    source_sha256: str | None
    source_page_count: int | None

    @property
    def included(self) -> bool:
        return self.status == "current"


@dataclass(frozen=True, slots=True)
class FeedbackAssemblyPlan:
    """Immutable, read-only preview for one assignment feedback assembly."""

    class_id: str
    assignment_id: str
    assignment_title: str
    scope: AssemblyScope
    output: AssemblyOutput
    duplex_safe: bool
    roster_count: int
    items: tuple[FeedbackAssemblyStudentPlan, ...]

    @property
    def selected_count(self) -> int:
        return len(self.items)

    @property
    def included_count(self) -> int:
        return sum(item.included for item in self.items)

    @property
    def excluded_count(self) -> int:
        return self.selected_count - self.included_count

    @property
    def reason_counts(self) -> tuple[tuple[str, int], ...]:
        counts = Counter(item.reason_code for item in self.items if not item.included)
        return tuple(sorted(counts.items()))


@dataclass(frozen=True, slots=True)
class FeedbackAssemblyExclusion:
    """One student omitted from the final artifact set."""

    student_id: str
    display_name: str
    reason_code: str


@dataclass(frozen=True, slots=True)
class FeedbackAssemblyResult:
    """Verified result of one atomic feedback-batch installation."""

    class_id: str
    assignment_id: str
    assignment_title: str
    scope: AssemblyScope
    output: AssemblyOutput
    duplex_safe: bool
    selected_count: int
    included_student_ids: tuple[str, ...]
    exclusions: tuple[FeedbackAssemblyExclusion, ...]
    print_packet_relative_path: str | None
    sharing_bundle_relative_path: str | None
    print_packet_page_count: int | None
    sharing_bundle_pdf_count: int | None

    @property
    def reason_counts(self) -> tuple[tuple[str, int], ...]:
        counts = Counter(item.reason_code for item in self.exclusions)
        return tuple(sorted(counts.items()))


@dataclass(frozen=True, slots=True)
class _ValidatedSource:
    item: FeedbackAssemblyStudentPlan
    data: bytes
    page_count: int


def build_feedback_assembly_plan(
    workspace_root: str | Path,
    class_id: str,
    assignment_id: str,
    *,
    scope: AssemblyScope,
    output: AssemblyOutput,
    duplex_safe: bool = False,
    student_ids: tuple[str, ...] = (),
) -> FeedbackAssemblyPlan:
    """Inspect canonical roster and feedback state without writing anything."""
    _validate_options(scope, output, duplex_safe, student_ids)
    root = _resolved_root(workspace_root)
    try:
        queue = build_assignment_review_work_queue(root, class_id, assignment_id)
    except (ReviewWorkQueueError, OSError, ValueError) as error:
        raise BatchFeedbackAssemblyError(
            "Could not load canonical assignment roster state."
        ) from error
    selected = _selected_queue_items(queue, scope, student_ids)
    items = tuple(_inspect_student(root, item) for item in selected)
    return FeedbackAssemblyPlan(
        class_id=queue.class_id,
        assignment_id=queue.assignment_id,
        assignment_title=queue.assignment_title,
        scope=scope,
        output=output,
        duplex_safe=duplex_safe,
        roster_count=queue.roster_count,
        items=items,
    )


def execute_feedback_assembly(
    workspace_root: str | Path,
    plan: FeedbackAssemblyPlan,
    *,
    batch_id: str | None = None,
) -> FeedbackAssemblyResult:
    """Revalidate sources, stage all requested artifacts, and install atomically."""
    _validate_plan(plan)
    root = _resolved_root(workspace_root)
    try:
        queue = build_assignment_review_work_queue(
            root, plan.class_id, plan.assignment_id
        )
    except (ReviewWorkQueueError, OSError, ValueError) as error:
        raise BatchFeedbackAssemblyError(
            "Assembly preflight could not reload canonical assignment state."
        ) from error
    if queue.assignment_title != plan.assignment_title:
        raise BatchFeedbackAssemblyError(
            "Assignment state changed after preview; no batch was created."
        )
    current_by_id = {item.student_id: item for item in queue.items}
    planned_roster_order = tuple(item.student_id for item in plan.items)
    current_order = tuple(
        item.student_id for item in queue.items if item.student_id in planned_roster_order
    )
    if current_order != planned_roster_order:
        raise BatchFeedbackAssemblyError(
            "Canonical roster selection changed after preview; no batch was created."
        )

    exclusions = [
        FeedbackAssemblyExclusion(item.student_id, item.display_name, item.reason_code)
        for item in plan.items
        if not item.included
    ]
    validated: list[_ValidatedSource] = []
    for planned in plan.items:
        if not planned.included:
            continue
        queue_item = current_by_id.get(planned.student_id)
        if queue_item is None:
            exclusions.append(
                FeedbackAssemblyExclusion(
                    planned.student_id, planned.display_name, "state_changed"
                )
            )
            continue
        current = _inspect_student(root, queue_item)
        if not _same_source_state(planned, current):
            exclusions.append(
                FeedbackAssemblyExclusion(
                    planned.student_id, planned.display_name, "state_changed"
                )
            )
            continue
        try:
            data = _read_ordinary_file(
                root, root / current.source_relative_path
            )
            if sha256(data).hexdigest() != planned.source_sha256:
                raise BatchFeedbackAssemblyError("source bytes changed")
            page_count = _pdf_page_count(data)
            if page_count != planned.source_page_count:
                raise BatchFeedbackAssemblyError("source PDF pages changed")
        except (BatchFeedbackAssemblyError, OSError, ValueError):
            exclusions.append(
                FeedbackAssemblyExclusion(
                    planned.student_id, planned.display_name, "state_changed"
                )
            )
            continue
        validated.append(_ValidatedSource(current, data, page_count))

    if not validated:
        raise BatchFeedbackAssemblyError(
            "No current feedback PDFs remain available; run Batch Feedback Export "
            "for missing or stale students and preview again."
        )

    safe_batch_id = batch_id or datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    if not _BATCH_ID.fullmatch(safe_batch_id):
        raise BatchFeedbackAssemblyError(
            "batch_id must be a Windows-safe UTC timestamp like 20260920T211500Z."
        )
    paths = quillan_work_paths(root, plan.class_id, plan.assignment_id)
    batches_dir = paths.exports_dir / "feedback_batches"
    final_dir = batches_dir / safe_batch_id
    _preflight_output_chain(root, batches_dir)
    if os.path.lexists(final_dir):
        raise BatchFeedbackAssemblyError(
            "Output collision: the planned feedback batch directory already exists."
        )

    made_batches_dir = not batches_dir.exists()
    staging_dir: Path | None = None
    try:
        batches_dir.mkdir(parents=True, exist_ok=True)
        staging_dir = Path(
            tempfile.mkdtemp(prefix=f".{safe_batch_id}.", suffix=".staging", dir=batches_dir)
        )
        packet_pages: int | None = None
        zip_count: int | None = None
        if plan.output in {"print", "both"}:
            packet = staging_dir / "feedback_print_packet.pdf"
            packet_pages = _write_print_packet(
                packet, tuple(validated), duplex_safe=plan.duplex_safe
            )
            if _pdf_page_count(packet.read_bytes()) != packet_pages:
                raise BatchFeedbackAssemblyError("Staged print packet verification failed.")
        if plan.output in {"bundle", "both"}:
            bundle = staging_dir / "feedback_sharing_bundle.zip"
            zip_count = _write_sharing_bundle(bundle, tuple(validated))
            _verify_sharing_bundle(bundle, tuple(validated))
        if os.path.lexists(final_dir):
            raise BatchFeedbackAssemblyError(
                "Output collision: the feedback batch directory appeared during assembly."
            )
        os.replace(staging_dir, final_dir)
        staging_dir = None
    except BatchFeedbackAssemblyError:
        raise
    except OSError as error:
        raise BatchFeedbackAssemblyError(
            "Feedback batch staging or final installation failed."
        ) from error
    except Exception as error:
        raise BatchFeedbackAssemblyError(
            "Feedback batch assembly failed while composing requested artifacts."
        ) from error
    finally:
        if staging_dir is not None:
            shutil.rmtree(staging_dir, ignore_errors=True)
        if made_batches_dir:
            try:
                batches_dir.rmdir()
            except OSError:
                pass

    relative_dir = final_dir.relative_to(root).as_posix()
    return FeedbackAssemblyResult(
        class_id=plan.class_id,
        assignment_id=plan.assignment_id,
        assignment_title=plan.assignment_title,
        scope=plan.scope,
        output=plan.output,
        duplex_safe=plan.duplex_safe,
        selected_count=plan.selected_count,
        included_student_ids=tuple(source.item.student_id for source in validated),
        exclusions=tuple(exclusions),
        print_packet_relative_path=(
            f"{relative_dir}/feedback_print_packet.pdf"
            if plan.output in {"print", "both"}
            else None
        ),
        sharing_bundle_relative_path=(
            f"{relative_dir}/feedback_sharing_bundle.zip"
            if plan.output in {"bundle", "both"}
            else None
        ),
        print_packet_page_count=packet_pages,
        sharing_bundle_pdf_count=zip_count,
    )


def _validate_options(
    scope: str,
    output: str,
    duplex_safe: bool,
    student_ids: tuple[str, ...],
) -> None:
    if scope not in {"whole_class", "selected"}:
        raise BatchFeedbackAssemblyError(f"Unsupported assembly scope: {scope!r}")
    if output not in _OUTPUTS:
        raise BatchFeedbackAssemblyError(f"Unsupported assembly output: {output!r}")
    if not isinstance(duplex_safe, bool):
        raise BatchFeedbackAssemblyError("duplex_safe must be a boolean.")
    if duplex_safe and output == "bundle":
        raise BatchFeedbackAssemblyError(
            "Duplex-safe separation applies only to print or both output."
        )
    if scope == "whole_class" and student_ids:
        raise BatchFeedbackAssemblyError(
            "Whole-class scope does not accept explicit student IDs."
        )
    if scope == "selected" and not student_ids:
        raise BatchFeedbackAssemblyError(
            "Selected scope requires at least one explicit student ID."
        )
    if len(set(student_ids)) != len(student_ids):
        raise BatchFeedbackAssemblyError("Explicit student IDs must be unique.")


def _validate_plan(plan: FeedbackAssemblyPlan) -> None:
    if not isinstance(plan, FeedbackAssemblyPlan):
        raise BatchFeedbackAssemblyError("plan must be a FeedbackAssemblyPlan.")
    if plan.scope not in {"whole_class", "selected"}:
        raise BatchFeedbackAssemblyError("Assembly plan has an invalid scope.")
    if plan.output not in _OUTPUTS:
        raise BatchFeedbackAssemblyError("Assembly plan has an invalid output mode.")
    if plan.duplex_safe and plan.output == "bundle":
        raise BatchFeedbackAssemblyError(
            "Duplex-safe separation applies only to print or both output."
        )
    if plan.scope == "selected" and not plan.items:
        raise BatchFeedbackAssemblyError("Selected assembly plan is empty.")
    if len({item.student_id for item in plan.items}) != len(plan.items):
        raise BatchFeedbackAssemblyError("Assembly plan contains duplicate students.")


def _selected_queue_items(
    queue: AssignmentReviewWorkQueue,
    scope: AssemblyScope,
    student_ids: tuple[str, ...],
) -> tuple[ReviewWorkQueueItem, ...]:
    if scope == "whole_class":
        return queue.items
    known = {item.student_id for item in queue.items}
    unknown = tuple(student_id for student_id in student_ids if student_id not in known)
    if unknown:
        raise BatchFeedbackAssemblyError(
            "Explicit selection contains unknown roster student IDs: "
            + ", ".join(unknown)
        )
    requested = set(student_ids)
    return tuple(item for item in queue.items if item.student_id in requested)


def _inspect_student(
    root: Path,
    queue_item: ReviewWorkQueueItem,
) -> FeedbackAssemblyStudentPlan:
    relative = feedback_pdf_export_path(
        root,
        queue_item.class_id,
        queue_item.assignment_id,
        queue_item.student_id,
    ).relative_to(root).as_posix()
    empty = {
        "source_relative_path": relative,
        "review_updated_at": None,
        "source_review_updated_at": None,
        "source_size": None,
        "source_sha256": None,
        "source_page_count": None,
    }
    try:
        status = student_review_status_to_dict(
            build_student_review_status(
                root,
                queue_item.class_id,
                queue_item.assignment_id,
                queue_item.student_id,
            )
        )
    except (StudentReviewStatusError, OSError, ValueError):
        return _student_plan(queue_item, "unavailable", "feedback_unavailable", **empty)
    if (
        status["class_id"] != queue_item.class_id
        or status["assignment_id"] != queue_item.assignment_id
        or status["student_id"] != queue_item.student_id
    ):
        return _student_plan(queue_item, "identity_mismatch", "identity_mismatch", **empty)
    student = cast(dict[str, Any], status["student"])
    review = cast(dict[str, Any], status["review"])
    exports = cast(dict[str, Any], review["exports"])
    pdf = cast(dict[str, Any], exports["feedback_pdf"])
    warnings = tuple(str(value) for value in cast(list[object], status["warnings"]))
    if student.get("roster_status") != "rostered" or review.get("status") == "identity_mismatch":
        return _student_plan(queue_item, "identity_mismatch", "identity_mismatch", **empty)
    review_updated_at = _optional_string(review.get("updated_at"))
    source_updated_at = _optional_string(pdf.get("source_review_updated_at"))
    base = {
        **empty,
        "review_updated_at": review_updated_at,
        "source_review_updated_at": source_updated_at,
    }
    pdf_status = pdf.get("status")
    if pdf_status == "missing":
        return _student_plan(queue_item, "missing", "feedback_pdf_missing", **base)
    if pdf_status == "stale":
        return _student_plan(queue_item, "stale", "feedback_pdf_stale", **base)
    if pdf_status != "present":
        reason = "identity_mismatch" if "identity_mismatch" in warnings else "feedback_metadata_invalid"
        kind: AssemblyStatus = "identity_mismatch" if reason == "identity_mismatch" else "metadata_invalid"
        return _student_plan(queue_item, kind, reason, **base)
    if (
        pdf.get("metadata_present") is not True
        or pdf.get("file_present") is not True
        or pdf.get("path") != relative
        or not review_updated_at
        or source_updated_at != review_updated_at
        or review.get("status") != "valid"
    ):
        return _student_plan(
            queue_item, "metadata_invalid", "feedback_metadata_invalid", **base
        )
    try:
        data = _read_ordinary_file(root, root / relative)
        pages = _pdf_page_count(data)
    except (BatchFeedbackAssemblyError, OSError, ValueError):
        return _student_plan(
            queue_item, "source_pdf_unreadable", "source_pdf_unreadable", **base
        )
    return _student_plan(
        queue_item,
        "current",
        "current",
        **{
            **base,
            "source_size": len(data),
            "source_sha256": sha256(data).hexdigest(),
            "source_page_count": pages,
        },
    )


def _student_plan(
    item: ReviewWorkQueueItem,
    status: AssemblyStatus,
    reason_code: str,
    **values: object,
) -> FeedbackAssemblyStudentPlan:
    return FeedbackAssemblyStudentPlan(
        student_id=item.student_id,
        display_name=item.display_name,
        status=status,
        reason_code=reason_code,
        source_relative_path=cast(str, values["source_relative_path"]),
        review_updated_at=cast(str | None, values["review_updated_at"]),
        source_review_updated_at=cast(
            str | None, values["source_review_updated_at"]
        ),
        source_size=cast(int | None, values["source_size"]),
        source_sha256=cast(str | None, values["source_sha256"]),
        source_page_count=cast(int | None, values["source_page_count"]),
    )


def _same_source_state(
    planned: FeedbackAssemblyStudentPlan,
    current: FeedbackAssemblyStudentPlan,
) -> bool:
    return (
        current.status == "current"
        and current.student_id == planned.student_id
        and current.display_name == planned.display_name
        and current.source_relative_path == planned.source_relative_path
        and current.review_updated_at == planned.review_updated_at
        and current.source_review_updated_at == planned.source_review_updated_at
        and current.source_size == planned.source_size
        and current.source_sha256 == planned.source_sha256
        and current.source_page_count == planned.source_page_count
    )


def _write_print_packet(
    path: Path,
    sources: tuple[_ValidatedSource, ...],
    *,
    duplex_safe: bool,
) -> int:
    writer = PdfWriter()
    page_count = 0
    for index, source in enumerate(sources):
        reader = PdfReader(BytesIO(source.data), strict=False)
        if reader.is_encrypted:
            raise BatchFeedbackAssemblyError("A source feedback PDF is encrypted.")
        for page in reader.pages:
            writer.add_page(page)
            page_count += 1
        if duplex_safe and source.page_count % 2 == 1 and index < len(sources) - 1:
            last = reader.pages[-1]
            writer.add_blank_page(
                width=float(last.mediabox.width),
                height=float(last.mediabox.height),
            )
            page_count += 1
    try:
        with path.open("xb") as stream:
            writer.write(stream)
    except OSError as error:
        raise BatchFeedbackAssemblyError("Could not stage the print packet.") from error
    return page_count


def _write_sharing_bundle(
    path: Path,
    sources: tuple[_ValidatedSource, ...],
) -> int:
    names = _sharing_names(sources)
    try:
        with ZipFile(path, mode="x", compression=ZIP_DEFLATED) as archive:
            for source, name in zip(sources, names, strict=True):
                archive.writestr(name, source.data)
    except OSError as error:
        raise BatchFeedbackAssemblyError("Could not stage the sharing bundle.") from error
    return len(sources)


def _verify_sharing_bundle(
    path: Path,
    sources: tuple[_ValidatedSource, ...],
) -> None:
    expected_names = _sharing_names(sources)
    try:
        with ZipFile(path, mode="r") as archive:
            names = tuple(archive.namelist())
            if names != expected_names:
                raise BatchFeedbackAssemblyError("Sharing bundle member verification failed.")
            for source, name in zip(sources, names, strict=True):
                if PurePosixPath(name).name != name or archive.read(name) != source.data:
                    raise BatchFeedbackAssemblyError(
                        "Sharing bundle source-byte verification failed."
                    )
    except BatchFeedbackAssemblyError:
        raise
    except Exception as error:
        raise BatchFeedbackAssemblyError("Sharing bundle verification failed.") from error


def _sharing_names(sources: tuple[_ValidatedSource, ...]) -> tuple[str, ...]:
    used: set[str] = set()
    names: list[str] = []
    for source in sources:
        label = _safe_filename_component(source.item.display_name)
        base = f"{label}_feedback.pdf"
        candidate = base
        if candidate.casefold() in used:
            student = _safe_filename_component(source.item.student_id)
            candidate = f"{label}_{student}_feedback.pdf"
        counter = 2
        while candidate.casefold() in used:
            candidate = f"{label}_{student}_{counter}_feedback.pdf"
            counter += 1
        if PurePosixPath(candidate).name != candidate:
            raise BatchFeedbackAssemblyError("Unsafe sharing filename generated.")
        used.add(candidate.casefold())
        names.append(candidate)
    return tuple(names)


def _safe_filename_component(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode()
    normalized = _ILLEGAL_FILENAME.sub("_", normalized)
    normalized = re.sub(r"\s+", "_", normalized)
    normalized = re.sub(r"_+", "_", normalized).strip(" ._")
    return normalized[:120] or "Student"


def _pdf_page_count(data: bytes) -> int:
    try:
        reader = PdfReader(BytesIO(data), strict=False)
        if reader.is_encrypted:
            raise BatchFeedbackAssemblyError("Encrypted feedback PDFs are unavailable.")
        count = len(reader.pages)
    except BatchFeedbackAssemblyError:
        raise
    except Exception as error:
        raise BatchFeedbackAssemblyError("A source feedback PDF is unreadable.") from error
    if count < 1:
        raise BatchFeedbackAssemblyError("A source feedback PDF contains no pages.")
    return count


def _read_ordinary_file(root: Path, path: Path) -> bytes:
    try:
        relative = path.relative_to(root)
    except ValueError as error:
        raise BatchFeedbackAssemblyError("Source feedback path escaped the workspace.") from error
    current = root
    if is_link_like(root) or not root.is_dir():
        raise BatchFeedbackAssemblyError("Workspace root is not an ordinary directory.")
    for part in relative.parts:
        current = current / part
        if not os.path.lexists(current):
            raise BatchFeedbackAssemblyError("Source feedback PDF is missing.")
        if is_link_like(current):
            raise BatchFeedbackAssemblyError("Source feedback path contains a link.")
    if not path.is_file():
        raise BatchFeedbackAssemblyError("Source feedback path is not an ordinary file.")
    return path.read_bytes()


def _preflight_output_chain(root: Path, target: Path) -> None:
    try:
        relative = target.relative_to(root)
    except ValueError as error:
        raise BatchFeedbackAssemblyError("Batch output path escaped the workspace.") from error
    current = root
    if is_link_like(root) or not root.is_dir():
        raise BatchFeedbackAssemblyError("Workspace root is not an ordinary directory.")
    for part in relative.parts:
        current = current / part
        if not os.path.lexists(current):
            continue
        if is_link_like(current) or not current.is_dir():
            raise BatchFeedbackAssemblyError(
                "Batch output path contains a link or non-directory component."
            )


def _resolved_root(workspace_root: str | Path) -> Path:
    try:
        root = Path(workspace_root).resolve(strict=True)
    except (OSError, RuntimeError) as error:
        raise BatchFeedbackAssemblyError("Could not resolve the PDS workspace root.") from error
    if not root.is_dir():
        raise BatchFeedbackAssemblyError("PDS workspace root is not a directory.")
    return root


def _optional_string(value: object) -> str | None:
    return value if isinstance(value, str) else None


__all__ = (
    "AssemblyOutput",
    "AssemblyScope",
    "BatchFeedbackAssemblyError",
    "FeedbackAssemblyExclusion",
    "FeedbackAssemblyPlan",
    "FeedbackAssemblyResult",
    "FeedbackAssemblyStudentPlan",
    "build_feedback_assembly_plan",
    "execute_feedback_assembly",
)
