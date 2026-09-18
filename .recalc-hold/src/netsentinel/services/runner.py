"""Uma fonte por processo; não inicia trabalho ao importar os módulos de API."""
from threading import Event, Thread
import logging
from netsentinel.services.synthetic import SyntheticSource
from netsentinel.security.system import preflight, LinuxSystem


class SourceRunner:
    def __init__(self, app, lab_config=None, max_observations=None):
        self.app, self.lab_config, self.max_observations = app, lab_config, max_observations
        self.stop_event = Event()
        self.thread = None
        self.last_error = None

    def start(self):
        if self.thread is not None:
            raise RuntimeError('Fonte já iniciada.')
        mode = self.app.extensions['settings'].mode
        if mode == 'lab':
            if self.max_observations is None or self.max_observations < 1:
                raise ValueError('LAB_MAX_OBSERVATIONS positivo é obrigatório.')
            preflight(self.lab_config, 'sensor', LinuxSystem())
        self.app.extensions['repository'].interrupt_calibrations()
        self.app.extensions['source_runner'] = self
        self.thread = Thread(target=self._run, daemon=True, name='netsentinel-source')
        self.thread.start()

    def _run(self):
        pipeline = self.app.extensions['pipeline']
        try:
            if self.app.extensions['settings'].mode == 'lab':
                from netsentinel.capture.config import CaptureConfig
                from netsentinel.capture.service import CaptureService
                CaptureService(CaptureConfig(self.lab_config.interface, 8, self.max_observations, True),
                               pipeline.consume).run(self.stop_event)
            else:
                source = SyntheticSource()
                while not self.stop_event.is_set():
                    pipeline.consume(source.snapshot())
                    self.stop_event.wait(1)
        except Exception:
            self.last_error = 'source_stopped'
            logging.getLogger(__name__).exception('Fonte interrompida; calibração não deve prosseguir')
            try:
                pipeline.publish(dict(event='source_error', reason='source_stopped'))
            except Exception:
                logging.getLogger(__name__).exception('Não foi possível persistir erro da fonte')

    def stop(self):
        self.stop_event.set()
        if self.thread:
            self.thread.join(timeout=10)
