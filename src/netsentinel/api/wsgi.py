"""Factory Gunicorn de um worker para o ambiente cloud com dados sintéticos."""
import atexit
from netsentinel.api.app import create_app
from netsentinel.api.settings import Settings
from netsentinel.services.runner import SourceRunner


def create_service():
    settings = Settings.from_env()
    if settings.mode != 'cloud':
        raise ValueError('Factory cloud não aceita laboratório real.')
    app = create_app(settings)
    runner = SourceRunner(app)
    runner.start()
    atexit.register(runner.stop)
    return app
