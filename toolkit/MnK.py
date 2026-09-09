"""Retired uncoordinated input API; use Application and InputIntent."""
class _MigratedInput:
    def __init__(self, *args, **kwargs):
        raise RuntimeError('Legacy direct input is retired; use autonavy.app.Application and InputIntent')

Mouse = _MigratedInput
Keyboard = _MigratedInput
