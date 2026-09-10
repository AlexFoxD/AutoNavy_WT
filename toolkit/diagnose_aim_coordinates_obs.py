"""Diagnose AutoNavy aim coordinates against the real 1280x720 OBS frame.

Put this file in <repo>/toolkit and run from repository root while in battle.
Manually put your aiming sight exactly on the selected target circle before running.

Creates:
  logs/v2/aim-coordinates/raw.png
  logs/v2/aim-coordinates/overlay.png
  logs/v2/aim-coordinates/center_crop.png
  logs/v2/aim-coordinates/report.txt
"""
from __future__ import annotations

from pathlib import Path
import sys
import cv2

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from autonavy.vision.detectors import find_target_reticle


OUT = ROOT / "logs" / "v2" / "aim-coordinates"
OUT.mkdir(parents=True, exist_ok=True)

DEVICE = 4
WIDTH = 1280
HEIGHT = 720

cap = cv2.VideoCapture(DEVICE, cv2.CAP_DSHOW)
cap.set(cv2.CAP_PROP_FRAME_WIDTH, WIDTH)
cap.set(cv2.CAP_PROP_FRAME_HEIGHT, HEIGHT)
cap.set(cv2.CAP_PROP_FPS, 60)

frame = None
ok = False
for _ in range(30):
    ok, frame = cap.read()

reported = (
    cap.get(cv2.CAP_PROP_FRAME_WIDTH),
    cap.get(cv2.CAP_PROP_FRAME_HEIGHT),
    cap.get(cv2.CAP_PROP_FPS),
)
cap.release()

if not ok or frame is None:
    raise RuntimeError("OBS frame unavailable")

h, w = frame.shape[:2]
if (w, h) != (WIDTH, HEIGHT):
    raise RuntimeError(
        f"Wrong OBS size: delivered={w}x{h}, expected={WIDTH}x{HEIGHT}"
    )

cx, cy = w // 2, h // 2

# Same expanded area currently used by the reticle fallback:
# fire_roi=(370,200,910,510), expanded by detector patch.
left, top, right, bottom = 220, 70, 1060, 520
roi = frame[top:bottom, left:right]

found = find_target_reticle(roi)

overlay = frame.copy()

# True OBS/content center.
cv2.line(overlay, (cx - 35, cy), (cx + 35, cy), (0, 255, 0), 2)
cv2.line(overlay, (cx, cy - 35), (cx, cy + 35), (0, 255, 0), 2)
cv2.putText(
    overlay,
    f"OBS CENTER ({cx},{cy})",
    (cx + 12, cy + 32),
    cv2.FONT_HERSHEY_SIMPLEX,
    0.55,
    (0, 255, 0),
    2,
    cv2.LINE_AA,
)

lines = [
    f"delivered_shape={frame.shape!r}",
    f"reported_width_height_fps={reported!r}",
    f"obs_content_center=({cx},{cy})",
    f"reticle_search_roi=({left},{top},{right},{bottom})",
]

if found is None:
    lines.append("detector_result=None")
else:
    rx, ry, radius, confidence = found
    rx += left
    ry += top
    dx = rx - cx
    dy = ry - cy

    lines.extend([
        f"detector_center=({rx},{ry})",
        f"detector_radius={radius}",
        f"detector_confidence={confidence:.6f}",
        f"detector_error_from_obs_center=({dx},{dy})",
    ])

    cv2.circle(overlay, (rx, ry), radius + 5, (0, 0, 255), 3)
    cv2.line(overlay, (rx - 20, ry), (rx + 20, ry), (0, 0, 255), 2)
    cv2.line(overlay, (rx, ry - 20), (rx, ry + 20), (0, 0, 255), 2)
    cv2.putText(
        overlay,
        f"DETECTOR ({rx},{ry}) d=({dx},{dy})",
        (max(0, rx - 180), max(25, ry - radius - 18)),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.55,
        (0, 0, 255),
        2,
        cv2.LINE_AA,
    )

cv2.rectangle(overlay, (left, top), (right, bottom), (255, 255, 255), 1)

cv2.imwrite(str(OUT / "raw.png"), frame)
cv2.imwrite(str(OUT / "overlay.png"), overlay)

crop_pad_x = 260
crop_pad_y = 210
center_crop = frame[
    max(0, cy-crop_pad_y):min(h, cy+crop_pad_y),
    max(0, cx-crop_pad_x):min(w, cx+crop_pad_x),
]
cv2.imwrite(str(OUT / "center_crop.png"), center_crop)

report = "\n".join(lines) + "\n"
(OUT / "report.txt").write_text(report, encoding="utf-8")

print(report)
print("saved:", OUT / "raw.png")
print("saved:", OUT / "overlay.png")
print("saved:", OUT / "center_crop.png")
print("saved:", OUT / "report.txt")
