"""Retired standalone vJoy API; the coordinated InputController owns the device."""
class JSK:
    def __init__(self, *args, **kwargs):
        raise RuntimeError('Legacy joystick input is retired; submit axis intents through Application.input')
