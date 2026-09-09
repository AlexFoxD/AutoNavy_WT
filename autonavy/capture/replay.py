"""Finite synthetic replay. No hardware, network, implicit repeat, or actuation."""
from __future__ import annotations

import json
from pathlib import Path
import time

from autonavy.models import FramePacket


class ReplayCapture:
    def __init__(self, fixture: str | Path, *, max_frames: int | None = None):
        if max_frames is not None and (type(max_frames) is not int or max_frames <= 0):
            raise ValueError('Replay frame budget must be a positive integer')
        self.fixture = Path(fixture)
        self.max_frames = max_frames
        self.closed = False
        self.started = False
        self.source_generation = 0
        self.publication_id = 0
        self._index = 0
        self._manifest = None

    def start(self) -> None:
        if self.closed:
            raise RuntimeError('Replay is closed; construct a new capture source')
        if self.started:
            return
        manifest_path = self.fixture / 'manifest.json'
        try:
            if manifest_path.stat().st_size > 8_000_000:
                raise ValueError('Replay manifest exceeds 8 MB limit')
            data = json.loads(manifest_path.read_text(encoding='utf-8-sig'))
        except (OSError, json.JSONDecodeError) as exc:
            raise ValueError(f'Cannot read replay manifest {manifest_path}: {exc}') from exc
        keys = {'schema_version', 'synthetic', 'pixel_format', 'geometry_id', 'width', 'height', 'frames'}
        if not isinstance(data, dict) or set(data) != keys or type(data['schema_version']) is not int or data['schema_version'] != 1 or data['synthetic'] is not True:
            raise ValueError('Replay requires a schema_version=1 explicit synthetic manifest')
        channels = {'BGR': 3, 'BGRA': 4}.get(data['pixel_format']) if isinstance(data['pixel_format'], str) else None
        if channels is None or not isinstance(data['geometry_id'], str) or not data['geometry_id'].strip():
            raise ValueError('Replay pixel format or geometry identity is invalid')
        if any(type(data[key]) is not int or data[key] <= 0 for key in ('width', 'height')) or data['width'] * data['height'] > 33_177_600:
            raise ValueError('Replay frame dimensions are invalid or too large')
        if not isinstance(data['frames'], list) or not 1 <= len(data['frames']) <= 100_000:
            raise ValueError('Replay requires 1 to 100000 explicit frames')
        for frame in data['frames']:
            if not isinstance(frame, dict) or set(frame) != {'color'}:
                raise ValueError('Synthetic replay frames require only a color array')
            color = frame['color']
            if not isinstance(color, list) or len(color) != channels or any(type(v) is not int or not 0 <= v <= 255 for v in color):
                raise ValueError('Replay colors must match the pixel format with uint8 channels')
        self._manifest = data
        self._index = 0
        self.source_generation += 1
        self.started = True

    def read(self) -> FramePacket | None:
        if self.closed or not self.started:
            raise RuntimeError('Replay must be started before reading')
        data = self._manifest
        if self._index >= len(data['frames']) or (self.max_frames is not None and self._index >= self.max_frames):
            return None
        import numpy as np
        color = data['frames'][self._index]['color']
        # FramePacket performs the ownership copy once, from a broadcast view.
        pixels = np.broadcast_to(np.array(color, dtype=np.uint8), (data['height'], data['width'], len(color)))
        self.publication_id += 1
        packet = FramePacket(pixels, data['pixel_format'], self.publication_id,
                             self.source_generation, time.monotonic_ns(), data['geometry_id'],
                             source_sequence=self._index)
        self._index += 1
        return packet

    def stop(self) -> None:
        self.started = False

    def close(self) -> None:
        self.stop()
        self._manifest = None
        self.closed = True
