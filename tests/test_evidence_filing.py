"""Evidence filing exposes only the authoritative page-outcome boundary."""

from pathlib import Path

from quillan.evidence_filing import file_routed_response_evidence
from tests.observation_test_support import successful_image_page


def test_evidence_filing_delegates_to_observation_persistence(tmp_path: Path) -> None:
    persisted = file_routed_response_evidence(
        tmp_path, page_outcome=successful_image_page(tmp_path)
    )
    assert persisted.status == "created"
    assert persisted.observation_path.is_file()
    assert persisted.evidence_path.is_file()
