"""Immutable installed Core publication compatibility metadata for Quillan."""

from pds_core.publication_compatibility import (
    PublicationContractSupport,
    PublicationProducerProfile,
    validate_publication_producer_profile,
)
from pds_core.publication_records import PUBLICATION_RECORD_SCHEMA_VERSION

from quillan.pds_contract import (
    ACADEMIC_RESULT_MANIFEST_CONTRACT_VERSION,
    QUILLAN_ACADEMIC_WORK_CONTRACT_VERSION,
    QUILLAN_DISPLAY_NAME,
    QUILLAN_MODULE_ID,
)


def get_publication_producer_profile() -> PublicationProducerProfile:
    """Return Quillan's validated, metadata-only publication profile."""
    return validate_publication_producer_profile(
        PublicationProducerProfile(
            module_id=QUILLAN_MODULE_ID,
            display_name=QUILLAN_DISPLAY_NAME,
            supported_core_publication_schema_versions=frozenset(
                {PUBLICATION_RECORD_SCHEMA_VERSION}
            ),
            supported_academic_work_contract_versions=frozenset(
                {QUILLAN_ACADEMIC_WORK_CONTRACT_VERSION}
            ),
            publication_contracts=(
                PublicationContractSupport(
                    publication_kind="academic_result_set",
                    manifest_contract_versions=frozenset(
                        {ACADEMIC_RESULT_MANIFEST_CONTRACT_VERSION}
                    ),
                    supported_capabilities=frozenset({"standards_ratings"}),
                    source_record_contracts=(),
                    allows_missing_source_record=True,
                ),
            ),
        )
    )


__all__ = ["get_publication_producer_profile"]
