"""Read-only Quillan readiness provider for Core module-operations v1."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Final

from pds_core.classes import class_folder, load_class_roster
from pds_core.module_operations import (
    ModuleOperationsNotice,
    ModuleOperationsRequest,
    ModuleReadinessReport,
    validate_module_readiness_report,
)
from pds_core.rosters import RosterError, RosterReadError, RosterValidationError

from quillan._path_safety import is_link_like
from quillan.pds_contract import QUILLAN_MODULE_ID
from quillan.record_context import (
    QuillanRecordContextError,
    canonical_workspace_root,
)
from quillan.work_paths import (
    QuillanWorkPathError,
    preflight_quillan_work_collection,
)

_UNAVAILABLE_NOTICE_CODE: Final = "quillan_readiness_unavailable"
_CLASS_NOT_READY_NOTICE_CODE: Final = "quillan_class_not_ready"


def evaluate_quillan_readiness(
    request: ModuleOperationsRequest,
    /,
) -> ModuleReadinessReport:
    """Evaluate structural Quillan readiness without mutating workspace state."""
    if not isinstance(request, ModuleOperationsRequest):
        raise TypeError("request must be a ModuleOperationsRequest.")

    if request.workspace_root is None:
        return _unavailable_report(
            "Quillan readiness requires an explicit workspace."
        )

    try:
        root = canonical_workspace_root(request.workspace_root)
    except (OSError, QuillanRecordContextError):
        return _unavailable_report(
            "The supplied workspace cannot be inspected safely for Quillan readiness."
        )

    if request.class_id is None:
        return _ready_report()

    return _evaluate_class_readiness(root, request.class_id)


def _evaluate_class_readiness(root: Path, class_id: str) -> ModuleReadinessReport:
    try:
        folder = class_folder(root, class_id)
    except (TypeError, ValueError):
        return _unavailable_report(
            "The requested Quillan class identity cannot be inspected safely."
        )

    try:
        if not os.path.lexists(folder.class_dir):
            return _class_not_ready_report()
        if is_link_like(folder.class_dir):
            return _unavailable_report(
                "The requested Quillan class path cannot be inspected safely."
            )
        if not folder.class_dir.is_dir():
            return _class_not_ready_report()

        preflight_quillan_work_collection(root, class_id)

        if not os.path.lexists(folder.roster_path):
            return _class_not_ready_report()
        if is_link_like(folder.roster_path):
            return _unavailable_report(
                "The requested Quillan class roster cannot be inspected safely."
            )
        if not folder.roster_path.is_file():
            return _class_not_ready_report()
    except (OSError, QuillanWorkPathError):
        return _unavailable_report(
            "The requested Quillan class structure cannot be inspected safely."
        )

    try:
        load_class_roster(root, class_id)
    except RosterValidationError:
        return _class_not_ready_report()
    except RosterReadError:
        return _unavailable_report(
            "The requested Quillan class roster cannot be inspected safely."
        )
    except RosterError:
        return _unavailable_report(
            "The requested Quillan class cannot be evaluated safely."
        )

    return _ready_report()


def _ready_report() -> ModuleReadinessReport:
    return validate_module_readiness_report(
        ModuleReadinessReport(
            evaluation="evaluated",
            ready=True,
            notices=(),
        ),
        expected_module_id=QUILLAN_MODULE_ID,
    )


def _class_not_ready_report() -> ModuleReadinessReport:
    return validate_module_readiness_report(
        ModuleReadinessReport(
            evaluation="evaluated",
            ready=False,
            notices=(
                ModuleOperationsNotice(
                    code=_CLASS_NOT_READY_NOTICE_CODE,
                    summary=(
                        "The requested Quillan class is missing or structurally invalid."
                    ),
                ),
            ),
        ),
        expected_module_id=QUILLAN_MODULE_ID,
    )


def _unavailable_report(summary: str) -> ModuleReadinessReport:
    return validate_module_readiness_report(
        ModuleReadinessReport(
            evaluation="unavailable",
            ready=None,
            notices=(
                ModuleOperationsNotice(
                    code=_UNAVAILABLE_NOTICE_CODE,
                    summary=summary,
                ),
            ),
        ),
        expected_module_id=QUILLAN_MODULE_ID,
    )


__all__ = ["evaluate_quillan_readiness"]
