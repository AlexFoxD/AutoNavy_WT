"""Synthetic characterization of source 45fc36c computations; no legacy imports."""

import cv2
import numpy as np


def test_color_canny_expansion_preserves_match_location_and_score():
    image = np.random.default_rng(42).integers(0, 256, (160, 220, 3), dtype=np.uint8)
    template = image[35:75, 67:112].copy()
    image_edge = cv2.Canny(image, 100, 200)
    template_edge = cv2.Canny(template, 100, 200)
    legacy = cv2.matchTemplate(
        cv2.cvtColor(image_edge, cv2.COLOR_BGR2BGRA),
        cv2.cvtColor(template_edge, cv2.COLOR_BGR2BGRA),
        cv2.TM_CCOEFF_NORMED,
    )
    single = cv2.matchTemplate(image_edge, template_edge, cv2.TM_CCOEFF_NORMED)
    assert cv2.minMaxLoc(legacy)[3] == cv2.minMaxLoc(single)[3] == (67, 35)
    np.testing.assert_allclose(single, legacy, atol=2e-6)


def test_one_pixel_morphology_is_identity():
    mask = np.random.default_rng(24).integers(0, 2, (70, 60), dtype=np.uint8) * 255
    kernel = np.ones((1, 1), np.uint8)
    legacy = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)
    legacy = cv2.morphologyEx(legacy, cv2.MORPH_OPEN, kernel)
    np.testing.assert_array_equal(legacy, mask)


def test_pixelwise_hsv_can_crop_first_without_changing_pixels():
    image = np.random.default_rng(7).integers(0, 256, (720, 1280, 3), dtype=np.uint8)
    full = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)[200:510, 370:910]
    cropped = cv2.cvtColor(image[200:510, 370:910], cv2.COLOR_BGR2HSV)
    np.testing.assert_array_equal(full, cropped)
