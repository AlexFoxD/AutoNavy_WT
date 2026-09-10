"""Regression tests for current-HUD fire alignment tolerance."""
from autonavy.behavior import FIRE_ALIGNMENT_PX, fire_aligned


def test_live_characterized_alignment_is_accepted():
    # Closest live OBS sample from current WT HUD: center=(614,341)
    # against 1280x720 content center=(640,360).
    assert FIRE_ALIGNMENT_PX == 30
    assert fire_aligned(-26, -19)


def test_alignment_boundary_is_inclusive():
    assert fire_aligned(30, 30)
    assert fire_aligned(-30, -30)


def test_target_outside_alignment_is_rejected():
    assert not fire_aligned(31, 0)
    assert not fire_aligned(0, -31)


def test_nonfinite_alignment_is_rejected():
    assert not fire_aligned(float("nan"), 0)
    assert not fire_aligned(0, float("inf"))
