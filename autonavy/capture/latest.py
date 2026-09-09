"""A single retained owned packet, shared by consumers without further copies."""
import threading
from autonavy.models import FramePacket


class LatestFrameSlot:
    def __init__(self):
        self._condition = threading.Condition()
        self._packet = None
        self.closed = False

    def publish(self, packet: FramePacket) -> None:
        with self._condition:
            if self.closed:
                raise RuntimeError('Latest frame slot is closed')
            if self._packet is not None and (packet.source_generation, packet.publication_id) <= (self._packet.source_generation, self._packet.publication_id):
                raise ValueError('Publication identity must increase')
            self._packet = packet
            self._condition.notify_all()

    def read(self) -> FramePacket | None:
        with self._condition:
            return None if self.closed else self._packet

    def wait(self, *, after=None, timeout=None) -> FramePacket | None:
        with self._condition:
            def available():
                return self.closed or (self._packet is not None and (after is None or (self._packet.source_generation, self._packet.publication_id) > after))
            self._condition.wait_for(available, timeout)
            return self._packet if not self.closed and available() else None

    def close(self) -> None:
        with self._condition:
            self.closed = True
            self._packet = None
            self._condition.notify_all()
