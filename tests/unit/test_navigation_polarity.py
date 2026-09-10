"""Regression tests for live tactical-map polarity normalization."""
import cv2
import numpy as np

from autonavy.navigation import native


def _encoded_image(width=8,height=8):
    image=np.full((height,width,3),127,dtype=np.uint8)
    ok,data=cv2.imencode('.png',image)
    assert ok
    return data.tobytes()


class RecordingAdapter:
    def __init__(self,route=True):
        self.calls=[]
        self.route=route

    def find(self,grid,origin,goal):
        self.calls.append((grid.copy(),origin,goal))
        return (origin,goal) if self.route else None


def test_zero_class_endpoints_are_normalized_to_passable(monkeypatch):
    grid=np.full((4,4,3),255,dtype=np.uint8)
    grid[1,1]=0
    grid[2,2]=0
    monkeypatch.setattr(native,'prepare_map',lambda image:grid.copy())
    adapter=RecordingAdapter()

    route=native.plan_encoded(
        _encoded_image(),
        (.25,.25),
        (.50,.50),
        adapter=adapter,
    )

    assert route==((.25,.25),(.50,.50))
    assert len(adapter.calls)==1
    normalized,origin,goal=adapter.calls[0]
    assert origin==(1,1)
    assert goal==(2,2)
    assert np.all(normalized[1,1]==255)
    assert np.all(normalized[2,2]==255)
    assert np.all(normalized[0,0]==0)


def test_nonzero_class_keeps_native_zero_blocked_contract(monkeypatch):
    grid=np.zeros((4,4,3),dtype=np.uint8)
    grid[1,1]=255
    grid[2,2]=128
    monkeypatch.setattr(native,'prepare_map',lambda image:grid.copy())
    adapter=RecordingAdapter()

    route=native.plan_encoded(
        _encoded_image(),
        (.25,.25),
        (.50,.50),
        adapter=adapter,
    )

    assert route==((.25,.25),(.50,.50))
    normalized,_,_=adapter.calls[0]
    assert np.all(normalized[1,1]==255)
    assert np.all(normalized[2,2]==255)
    assert np.all(normalized[0,0]==0)


def test_mixed_endpoint_classes_are_rejected_without_native_call(monkeypatch):
    grid=np.full((4,4,3),255,dtype=np.uint8)
    grid[1,1]=0
    monkeypatch.setattr(native,'prepare_map',lambda image:grid.copy())
    adapter=RecordingAdapter()

    route=native.plan_encoded(
        _encoded_image(),
        (.25,.25),
        (.50,.50),
        adapter=adapter,
    )

    assert route is None
    assert adapter.calls==[]
