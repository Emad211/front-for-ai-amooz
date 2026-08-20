from __future__ import annotations

import json
import zipfile

from apps.classes.management.commands import replay_exam_prep_mistral_stage5 as replay


def test_targeted_bundle_caches_safe_recoveries_beyond_stage5_selection(tmp_path):
    bundle = tmp_path / "targeted.zip"
    root = {
        "pages": [
            {
                "index": 0,
                "blocks": [
                    {"type": "text", "content": "127- گزینه 3"},
                ],
            },
            {
                "index": 1,
                "blocks": [
                    {"type": "text", "content": "134- گزینه 1"},
                    {"type": "text", "content": "135- گزینه 2"},
                    {"type": "text", "content": "136- گزینه 2"},
                    {"type": "text", "content": "137- گزینه 4"},
                    {"type": "text", "content": "138- گزینه 3"},
                ],
            },
        ]
    }
    request = {
        "source": {
            "cropSpecs": [
                {"physicalPageNumber": 11, "column": "left"},
                {"physicalPageNumber": 13, "column": "right"},
            ]
        }
    }
    manifest = {
        "providerRequestCount": 1,
        "retryCount": 0,
        "estimatedCost": {"unit": "0.004"},
    }
    with zipfile.ZipFile(bundle, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("response.raw.json", json.dumps(root))
        archive.writestr("request.safe.json", json.dumps(request))
        archive.writestr("manifest.json", json.dumps(manifest))

    recovered, cached = replay._load_cached_targeted_recovery(
        bundle_path=bundle,
        targets=frozenset({(134, "solution"), (135, "solution")}),
    )

    assert recovered == {
        127: ("3", 11, "left"),
        134: ("1", 13, "right"),
        135: ("2", 13, "right"),
        136: ("2", 13, "right"),
        137: ("4", 13, "right"),
        138: ("3", 13, "right"),
    }
    assert cached.crop_specs == ((11, "left"), (13, "right"))
    assert cached.provider_call_count == 1
    assert str(cached.estimated_cost_unit) == "0.004"
