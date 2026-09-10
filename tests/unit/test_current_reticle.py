"""Regression tests for the current naval selected-enemy reticle detector."""
import cv2
import numpy as np

from autonavy.vision.detectors import find_target_reticle


def test_current_reticle_circle_with_hostile_context_is_detected():
    image = np.full((450, 840, 3), (80, 100, 110), dtype=np.uint8)

    cv2.circle(image, (421, 129), 21, (210, 210, 210), 2, cv2.LINE_AA)
    cv2.line(image, (410, 129), (432, 129), (190, 190, 190), 1, cv2.LINE_AA)
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


def test_generic_circle_without_hostile_red_context_is_rejected():
    image = np.full((450, 840, 3), (80, 100, 110), dtype=np.uint8)
    cv2.circle(image, (421, 129), 21, (210, 210, 210), 2, cv2.LINE_AA)

    assert find_target_reticle(image) is None


def test_red_hostile_context_without_ring_is_rejected():
    image = np.full((450, 840, 3), (80, 100, 110), dtype=np.uint8)

    cv2.putText(
        image, 'ENEMY', (385, 92),
        cv2.FONT_HERSHEY_SIMPLEX, .45, (0, 0, 255), 1, cv2.LINE_AA,
    )
    cv2.rectangle(image, (395, 108), (447, 142), (210, 210, 210), 2)

    assert find_target_reticle(image) is None


def test_precomputed_edges_avoid_local_canny(monkeypatch):
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

    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    edges = cv2.Canny(gray, 80, 160)

    def forbidden(*args, **kwargs):
        raise AssertionError('find_target_reticle must reuse supplied edges')

    monkeypatch.setattr(cv2, 'Canny', forbidden)

    result = find_target_reticle(image, edge_map=edges)
    assert result is not None
