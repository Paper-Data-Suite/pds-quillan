"""Installed Quillan module-operations profile for Core v1."""

from __future__ import annotations

from pds_core.module_operations import (
    MODULE_OPERATIONS_CONTRACT_VERSION,
    ModuleAttentionReport,
    ModuleOperationsProfile,
    ModuleOperationsRequest,
    validate_module_operations_profile,
)

from quillan.pds_contract import QUILLAN_MODULE_ID


def evaluate_quillan_attention(
    request: ModuleOperationsRequest,
    /,
) -> ModuleAttentionReport:
    """Lazily evaluate Quillan-owned attention for one neutral Core request."""
    from quillan.attention_provider import evaluate_quillan_attention as _evaluate

    return _evaluate(request)


def get_module_operations_profile() -> ModuleOperationsProfile:
    """Return Quillan's validated attention-only Core operations profile."""
    return validate_module_operations_profile(
        ModuleOperationsProfile(
            module_id=QUILLAN_MODULE_ID,
            supported_core_operations_contract_versions=frozenset(
                {MODULE_OPERATIONS_CONTRACT_VERSION}
            ),
            readiness_provider=None,
            attention_provider=evaluate_quillan_attention,
        )
    )


__all__ = ["evaluate_quillan_attention", "get_module_operations_profile"]
