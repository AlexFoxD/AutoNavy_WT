"""Focused tests for dual-mode current WT naval target marker detection."""
import cv2
import numpy as np

from autonavy.vision.detectors import (
    find_close_target_marker,
    find_target_reticle,
)


def test_close_target_red_hud_pair_maps_to_aim_point():
    image = np.zeros((450, 840, 3), dtype=np.uint8)

    # Live characterization, translated into ROI-local coordinates:
    # upper band center ~ (416, 189), lower ~ (415, 359).
    cv2.rectangle(image, (398, 184), (433, 193), (0, 0, 255), -1)
    cv2.rectangle(image, (394, 354), (435, 363), (0, 0, 255), -1)

    result = find_close_target_marker(image)

    assert result is not None
    x, y, radius, confidence = result
    assert abs(x - 415) <= 2
    assert abs(y - 290) <= 2
    assert radius == 12
    assert confidence > .5


def test_close_target_requires_horizontal_alignment():
    image = np.zeros((450, 840, 3), dtype=np.uint8)
    cv2.rectangle(image, (250, 184), (285, 193), (0, 0, 255), -1)
    cv2.rectangle(image, (420, 354), (461, 363), (0, 0, 255), -1)

    assert find_close_target_marker(image) is None


def test_close_target_rejects_far_hud_vertical_gap():
    image = np.zeros((450, 840, 3), dtype=np.uint8)
    cv2.rectangle(image, (398, 80), (440, 91), (0, 0, 255), -1)
    cv2.rectangle(image, (398, 136), (440, 147), (0, 0, 255), -1)

    assert find_close_target_marker(image) is None


def test_distant_circle_mode_still_works():
    image = np.full((450, 840, 3), (80, 100, 110), dtype=np.uint8)

    cv2.circle(image, (421, 129), 21, (210, 210, 210), 2, cv2.LINE_AA)
    cv2.putText(
        image, 'ENEMY', (385, 92),
        cv2.FONT_HERSHEY_SIMPLEX, .45, (0, 0, 255), 1, cv2.LINE_AA,
    )
    cv2.putText(
        image, '2.1 km', (397, 165),
        cv2.FONT_HERSHEY_SIMPLEX, .4, (0, 0, 255), 1, cv2.LINE_AA,
    )

    result = find_target_reticle(image)

    assert result is not None
    x, y, radius, confidence = result
    assert abs(x - 421) <= 3
    assert abs(y - 129) <= 3
    assert 16 <= radius <= 28
    assert confidence > .5


def test_unrelated_circle_without_hostile_context_is_rejected():
    image = np.full((450, 840, 3), (80, 100, 110), dtype=np.uint8)
    cv2.circle(image, (421, 129), 21, (210, 210, 210), 2, cv2.LINE_AA)

    assert find_target_reticle(image) is None


def test_precomputed_edges_avoid_local_canny(monkeypatch):
    image = np.full((450, 840, 3), (80, 100, 110), dtype=np.uint8)
    cv2.circle(image, (421, 129), 21, (210, 210, 210), 2, cv2.LINE_AA)
    cv2.putText(
        image, 'ENEMY', (385, 92),
        cv2.FONT_HERSHEY_SIMPLEX, .45, (0, 0, 255), 1, cv2.LINE_AA,
    )

    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    edges = cv2.Canny(gray, 80, 160)

    def forbidden(*args, **kwargs):
        raise AssertionError('runtime path must reuse supplied edges')

    monkeypatch.setattr(cv2, 'Canny', forbidden)

    # No close-range paired bands, so this exercises strict circle mode.
    find_target_reticle(image, edge_map=edges)
