"""Observer em processo único; persistir o evento antes de notificar assinantes."""
from threading import RLock
import logging


class EventBus:
    def __init__(self):
        self._subscribers = []
        self._lock = RLock()

    def subscribe(self, callback):
        with self._lock:
            self._subscribers.append(callback)

        def unsubscribe():
            with self._lock:
                if callback in self._subscribers:
                    self._subscribers.remove(callback)
        return unsubscribe

    def publish(self, event):
        with self._lock:
            callbacks = tuple(self._subscribers)
        for callback in callbacks:
            try:
                callback(event)
            except Exception:
                # Queda de um assinante não impede os demais; replay vem do Repository.
                logging.getLogger(__name__).exception('Falha de assinante de eventos')
