"""Integra captura, Repository, fuzzy e a Strategy já aprovada."""
from threading import RLock
from time import time
from netsentinel.analysis.fuzzy import FuzzyRiskStrategy
from netsentinel.security.demo import SecurityDemo


class BackendPipeline:
    def __init__(self, repository, bus, identity, mitigation, mode):
        self.repository, self.bus, self.mode = repository, bus, mode
        self.lock = RLock()
        self.latest = None
        self.security = SecurityDemo(identity, FuzzyRiskStrategy(repository, repository),
                                     mitigation, self.publish)

    def publish(self, event):
        payload = dict(event, timestamp=event.get('timestamp', time()),
                       source='live' if self.mode == 'lab' else 'synthetic')
        saved = self.repository.append_event(payload)
        self.bus.publish(saved)

    def consume(self, snapshot):
        expected = 'live' if self.mode == 'lab' else 'synthetic'
        if snapshot['source'] != expected:
            raise ValueError('Fonte de dados incompatível com o ambiente.')
        with self.lock:
            self.repository.save_snapshot(snapshot)
            self.latest = snapshot
            # Classificar com o baseline anterior: nunca treinar com a janela e
            # compará-la imediatamente contra um baseline que já a contém.
            self.security.consume(snapshot)
            for completed in self.repository.collect_calibration(snapshot):
                self.publish(dict(event='baseline_calibrated', **completed))
            self.publish(dict(event='snapshot_updated', snapshot=snapshot))
