"""Orquestração síncrona; consumidores devem ser rápidos e não bloqueantes."""
from time import monotonic, time
from uuid import uuid4
from netsentinel.capture.normalizer import normalize
from netsentinel.capture.scapy_source import ScapySource
from netsentinel.capture.window import ObservationWindow


class CaptureService:
    def __init__(self, config, publish, clock=monotonic, source_factory=ScapySource):
        self.config, self.publish, self.clock = config, publish, clock
        self.source_factory = source_factory
        self.window = ObservationWindow(config.window_seconds, config.max_observations)
        self.unsupported_total = 0
        self.malformed_total = 0
        self.started_at = None
        self.run_id = uuid4().hex

    def _start_clock(self):
        if self.started_at is None:
            self.started_at = self.clock()

    def ingest(self, packet):
        self._start_clock()
        try:
            observation = normalize(packet)
        except (ValueError, TypeError, AttributeError, IndexError):
            self.malformed_total += 1
            return
        if observation is None:
            self.unsupported_total += 1
            return
        self.window.add(observation, self.clock())

    def emit(self):
        self._start_clock()
        now = self.clock()
        snapshot = self.window.snapshot(now)
        elapsed = max(0.0, now - self.started_at)
        snapshot.update(capture_run_id=self.run_id, window_end_monotonic=now,
                        window_start_monotonic=now - min(elapsed, self.config.window_seconds),
                        observed_seconds=min(elapsed, self.config.window_seconds),
                        warming_up=elapsed < self.config.window_seconds)
        snapshot.update(timestamp=time(), source="live", interface=self.config.interface,
                        unsupported_total=self.unsupported_total,
                        malformed_total=self.malformed_total)
        self.publish(snapshot)

    def run(self, stop):
        # Erros de permissão e abertura propagam: falha não pode parecer rede silenciosa.
        with self.source_factory(self.config.interface) as source:
            self._start_clock()
            try:
                while not stop.is_set():
                    source.poll(self.ingest)
                    self.emit()
            finally:
                self.emit()
