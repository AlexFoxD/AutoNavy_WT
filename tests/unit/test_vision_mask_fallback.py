"""Focused regression tests for battle vision mask fallback."""
from autonavy.vision import detectors


def _obs(score, matched=False):
    return detectors.MatchObservation(
        1, 1, "geometry", True, matched, score,
        (1, 1, 3, 3) if matched else None,
    )


def test_mask_fallback_keeps_masked_match_without_plain_retry(monkeypatch):
    template_calls = []
    plain_calls = []

    def masked(*args, **kwargs):
        template_calls.append(kwargs.get("mask"))
        return _obs(.91, True)

    def plain(*args, **kwargs):
        plain_calls.append(True)
        return _obs(.95, True)

    monkeypatch.setattr(detectors, "match_template", masked)
    monkeypatch.setattr(detectors, "_match_precomputed_edges", plain)

    result = detectors.match_template_with_mask_fallback(
        object(), object(), "aim", (0, 0, 10, 10), .3,
        mask=((1, 2, 3), (4, 5, 6), 1),
        fallback_edges=object(),
        fallback_rect=(0, 0, 20, 20),
    )

    assert result.matched
    assert result.score == .91
    assert len(template_calls) == 1
    assert plain_calls == []


def test_mask_fallback_uses_precomputed_edges_without_second_match_template(monkeypatch):
    template_calls = []
    plain_calls = []

    def masked(*args, **kwargs):
        template_calls.append(kwargs.get("mask"))
        return _obs(0.0, False)

    def plain(*args, **kwargs):
        plain_calls.append(True)
        return _obs(.72, True)

    monkeypatch.setattr(detectors, "match_template", masked)
    monkeypatch.setattr(detectors, "_match_precomputed_edges", plain)

    result = detectors.match_template_with_mask_fallback(
        object(), object(), "aim", (0, 0, 10, 10), .3,
        mask=((1, 2, 3), (4, 5, 6), 1),
        fallback_edges=object(),
        fallback_rect=(0, 0, 20, 20),
    )

    assert result.matched
    assert result.score == .72
    assert len(template_calls) == 1
    assert len(plain_calls) == 1


def test_mask_fallback_keeps_better_unmatched_score(monkeypatch):
    monkeypatch.setattr(
        detectors,
        "match_template",
        lambda *a, **k: _obs(.02, False),
    )
    monkeypatch.setattr(
        detectors,
        "_match_precomputed_edges",
        lambda *a, **k: _obs(.24, False),
    )

    result = detectors.match_template_with_mask_fallback(
        object(), object(), "lock", (0, 0, 10, 10), .3,
        mask=((0, 0, 0), (180, 255, 46), 1),
        fallback_edges=object(),
        fallback_rect=(0, 0, 20, 20),
    )

    assert not result.matched
    assert result.score == .24
