from __future__ import annotations

from apps.classes.services import exam_prep_mistral_visual_reconcile_v3 as policy


def test_strong_solution_cluster_accepts_structural_diagram_component():
    region = {
        "kind": "solution",
        "questionNumber": 133,
        "bbox": [0.50, 0.10, 1.0, 0.80],
    }
    components = [
        {
            "bbox": [0.58, 0.30, 0.82, 0.56],
            "inkPixels": 1800,
            "widthPx": 240,
            "heightPx": 180,
        }
    ]
    clusters = policy._strong_solution_clusters(region=region, components=components)
    assert len(clusters) == 1


def test_strong_solution_cluster_rejects_small_residual_word_glyphs():
    region = {
        "kind": "solution",
        "questionNumber": 33,
        "bbox": [0.0, 0.10, 0.50, 0.80],
    }
    components = [
        {
            "bbox": [0.20, 0.25, 0.24, 0.27],
            "inkPixels": 45,
            "widthPx": 40,
            "heightPx": 16,
        },
        {
            "bbox": [0.25, 0.25, 0.29, 0.27],
            "inkPixels": 50,
            "widthPx": 40,
            "heightPx": 16,
        },
    ]
    assert policy._strong_solution_clusters(region=region, components=components) == []
