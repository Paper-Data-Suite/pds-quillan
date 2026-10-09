"""Qualify installed Core 0.6.5 reader declarations without sibling consumers."""

from __future__ import annotations

import argparse
import json
import sys
from importlib import metadata
from pathlib import Path

from pds_core.publication_compatibility import (
    evaluate_publication_compatibility,
    lookup_publication_reader_support,
    validate_publication_producer_profile,
)
from quillan.academic_result_reader import (
    QuillanAcademicResultReaderDecodeError,
    read_academic_result_manifest,
)
from quillan.pds_publication import get_publication_producer_profile


CORE_VERSION = "0.6.5"
QUILLAN_VERSION = "0.10.6"
MANIFEST = "quillan_academic_result_manifest_v1"
READER = "quillan_academic_result_reader_v1"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fixture", type=Path, required=True)
    parser.add_argument("--repository", type=Path, required=True)
    args = parser.parse_args()

    assert metadata.version("pds-core") == CORE_VERSION
    assert metadata.version("quillan") == QUILLAN_VERSION
    repository = args.repository.resolve(strict=True)
    for package_name in ("pds_core", "quillan"):
        installed = __import__(package_name)
        origin_text = getattr(installed, "__file__", None)
        assert isinstance(origin_text, str)
        origin = Path(origin_text).resolve(strict=True)
        assert origin.is_relative_to(Path(sys.prefix).resolve())
        assert not origin.is_relative_to(repository), "source shadowing"

    entry_points = tuple(metadata.entry_points().select(
        group="paper_data_suite.publication_producers", name="quillan"
    ))
    assert len(entry_points) == 1
    provider = entry_points[0].load()
    assert provider() == get_publication_producer_profile()
    profile = validate_publication_producer_profile(provider())
    support = lookup_publication_reader_support(
        profile, "academic_result_set", MANIFEST
    )
    assert support is not None
    assert support.distribution_name == "quillan"
    assert support.manifest_contract_version == MANIFEST
    assert support.reader_contract_version == READER
    assert (
        lookup_publication_reader_support(profile, "intervention_record_set", MANIFEST)
        is None
    )
    assert (
        lookup_publication_reader_support(
            profile, "academic_result_set", "unadvertised_manifest_v2"
        ) is None
    )

    raw = args.fixture.resolve(strict=True).read_bytes()
    value = read_academic_result_manifest(raw)
    assert value.contract_version == MANIFEST
    assert value.producer_module_id == "quillan"
    try:
        read_academic_result_manifest(b"not JSON")
    except QuillanAcademicResultReaderDecodeError:
        pass
    else:
        raise AssertionError("invalid bytes did not fail closed")

    # Pure metadata does not claim authorization or consumer support.
    assert not hasattr(support, "callback")
    assert not hasattr(support, "read")
    assert callable(evaluate_publication_compatibility)
    assert not ({"meridian", "vitrine"} & set(sys.modules))
    print(json.dumps({
        "issue": 421, "status": "PASS", "core": CORE_VERSION,
        "quillan": QUILLAN_VERSION, "reader_contract": READER,
        "manifest_contract": MANIFEST, "source_isolated": True,
    }, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
