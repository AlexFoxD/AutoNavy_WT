"""Capture current WT collision/recovery HUD from OBS for detector repair.

Put in <repo>/toolkit and run from repository root WHILE the crash/stuck
warning is visibly present on screen:

    .\.venv\Scripts\python.exe .\toolkit\capture_recovery_marker_obs.py

It captures ~2 seconds from OBS and keeps the frame with the strongest red
signal inside the same collision ROI used by VisionPipeline.

Output:
  logs/v2/recovery-marker/raw.png
  logs/v2/recovery-marker/collision_roi.png
  logs/v2/recovery-marker/current_mask.png
  logs/v2/recovery-marker/full_red_mask.png
  logs/v2/recovery-marker/report.txt
  logs/v2/recovery-marker/templates/   (matching crash/collision assets, if found)
"""
from __future__ import annotations

from pathlib import Path
import shutil
import cv2
import numpy as np


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "logs" / "v2" / "recovery-marker"
TPL_OUT = OUT / "templates"
OUT.mkdir(parents=True, exist_ok=True)
TPL_OUT.mkdir(parents=True, exist_ok=True)

DEVICE = 4
WIDTH = 1280
HEIGHT = 720
FRAMES = 120

cap = cv2.VideoCapture(DEVICE, cv2.CAP_DSHOW)
cap.set(cv2.CAP_PROP_FRAME_WIDTH, WIDTH)
cap.set(cv2.CAP_PROP_FRAME_HEIGHT, HEIGHT)
cap.set(cv2.CAP_PROP_FPS, 60)

best = None
best_score = -1
best_index = -1
delivered = 0

for i in range(FRAMES):
    ok, frame = cap.read()
    if not ok or frame is None:
        continue

    delivered += 1
    h, w = frame.shape[:2]
    if (w, h) != (WIDTH, HEIGHT):
        continue

    x1, x2 = w // 3, (w // 3) * 2
    roi = frame[:, x1:x2]

    hsv = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)

    # Exact current runtime crash detector mask.
    current = cv2.inRange(hsv, (0, 43, 46), (10, 255, 255))

    # Diagnostic red mask including hue wraparound.
    high_red = cv2.inRange(hsv, (165, 43, 46), (180, 255, 255))
    full_red = cv2.bitwise_or(current, high_red)

    # Weight the central half vertically a little more; collision text is
    # normally a HUD element rather than minimap/top-bar decoration.
    mid = full_red[h // 5: h * 4 // 5]
    score = int(np.count_nonzero(full_red)) + 2 * int(np.count_nonzero(mid))

    if score > best_score:
        best_score = score
        best_index = i
        best = frame.copy()

cap.release()

if best is None:
    raise RuntimeError("No usable OBS frame captured")

h, w = best.shape[:2]
x1, x2 = w // 3, (w // 3) * 2
roi = best[:, x1:x2]
hsv = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)

current_mask = cv2.inRange(hsv, (0, 43, 46), (10, 255, 255))
high_red_mask = cv2.inRange(hsv, (165, 43, 46), (180, 255, 255))
full_red_mask = cv2.bitwise_or(current_mask, high_red_mask)

cv2.imwrite(str(OUT / "raw.png"), best)
cv2.imwrite(str(OUT / "collision_roi.png"), roi)
cv2.imwrite(str(OUT / "current_mask.png"), current_mask)
cv2.imwrite(str(OUT / "full_red_mask.png"), full_red_mask)

# Report hue distribution for reasonably saturated/bright pixels.
sat = hsv[:, :, 1]
val = hsv[:, :, 2]
interesting = (sat >= 43) & (val >= 46)
hues = hsv[:, :, 0][interesting]
hist = np.bincount(hues, minlength=181) if hues.size else np.zeros(181, dtype=int)
top_hues = sorted(
    ((int(count), int(hue)) for hue, count in enumerate(hist) if count),
    reverse=True
)[:20]

# Copy any likely legacy crash/collision templates so they can be inspected
# alongside the live frame without guessing exact filenames.
templates_root = ROOT / "src" / "game_image"
copied = []
if templates_root.exists():
    for candidate in templates_root.rglob("*"):
        if not candidate.is_file():
            continue
        lower = candidate.name.lower()
        if any(key in lower for key in ("crash", "collision", "stuck")):
            dest = TPL_OUT / candidate.name
            try:
                shutil.copy2(candidate, dest)
                copied.append(str(candidate.relative_to(ROOT)))
            except OSError:
                pass

report = [
    f"delivered_frames={delivered}",
    f"selected_frame_index={best_index}",
    f"selected_red_score={best_score}",
    f"shape={best.shape!r}",
    f"collision_roi=({x1},0,{x2},{h})",
    f"current_mask_pixels={int(np.count_nonzero(current_mask))}",
    f"high_red_mask_pixels={int(np.count_nonzero(high_red_mask))}",
    f"full_red_mask_pixels={int(np.count_nonzero(full_red_mask))}",
    "top_hues=count:hue",
]
report.extend(f"  {count}:{hue}" for count, hue in top_hues)
report.append("copied_templates:")
report.extend(f"  {name}" for name in copied)
report_text = "\n".join(report) + "\n"

(OUT / "report.txt").write_text(report_text, encoding="utf-8")

print(report_text)
print("saved:", OUT)
