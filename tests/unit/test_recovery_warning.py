"""Tests for the current WT shallow-water recovery warning."""
import cv2
import numpy as np

from autonavy.vision.detectors import find_shallow_water_warning


ORANGE = (0, 165, 255)  # BGR, HSV hue ~19


def frame():
    return np.zeros((720, 1280, 3), dtype=np.uint8)


def test_wide_orange_warning_with_shallow_context_is_detected():
    image = frame()

    # Approximate current live HUD geometry.
    cv2.putText(
        image,
        'Dangerously low depth on course',
        (470, 137),
        cv2.FONT_HERSHEY_SIMPLEX,
        .70,
        ORANGE,
        2,
        cv2.LINE_AA,
    )

    # Shallow-water icon/context below warning.
    cv2.circle(image, (650, 210), 16, ORANGE, -1)
    cv2.rectangle(image, (635, 225), (665, 237), ORANGE, -1)

    result = find_shallow_water_warning(image)

    assert result is not None
    box, confidence = result
    assert box[0] < 650 < box[2]
    assert 100 <= box[1] <= 145
    assert confidence >= .5


def test_wide_orange_notification_without_shallow_icon_is_rejected():
    image = frame()
    cv2.putText(
        image,
        'Dangerously low depth on course',
        (470, 137),
        cv2.FONT_HERSHEY_SIMPLEX,
        .70,
        ORANGE,
        2,
        cv2.LINE_AA,
    )

    assert find_shallow_water_warning(image) is None


def test_shallow_icon_without_warning_text_is_rejected():
    image = frame()
    cv2.circle(image, (650, 210), 16, ORANGE, -1)
    cv2.rectangle(image, (635, 225), (665, 237), ORANGE, -1)

    assert find_shallow_water_warning(image) is None


def test_red_hud_text_is_not_misclassified_as_shallow_warning():
    image = frame()
    cv2.putText(
        image,
        'ENEMY TARGET',
        (500, 137),
        cv2.FONT_HERSHEY_SIMPLEX,
        .9,
        (0, 0, 255),
        2,
        cv2.LINE_AA,
    )
    cv2.circle(image, (650, 210), 16, (0, 0, 255), -1)

    assert find_shallow_water_warning(image) is None
