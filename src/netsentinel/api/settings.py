"""Ambientes separados e credenciais obrigatórias, sem defaults secretos."""
from dataclasses import dataclass
import os
from sqlalchemy.engine import make_url


@dataclass(frozen=True)
class Settings:
    mode: str
    database_url: str
    secret_key: str
    operator_username: str
    operator_password_hash: str

    def __post_init__(self):
        if self.mode not in ('lab', 'cloud'):
            raise ValueError('APP_MODE deve ser lab ou cloud.')
        if len(self.secret_key) < 32 or not 1 <= len(self.operator_username) <= 120:
            raise ValueError('Configure SECRET_KEY forte e OPERATOR_USERNAME.')
        if not self.operator_password_hash.startswith(('scrypt:', 'pbkdf2:')):
            raise ValueError('OPERATOR_PASSWORD_HASH deve ser um hash Werkzeug.')
        url = make_url(self.database_url)
        if url.drivername == 'postgresql':
            object.__setattr__(self, 'database_url', str(url.set(drivername='postgresql+psycopg').render_as_string(hide_password=False)))
        if url.get_backend_name() not in ('sqlite', 'postgresql'):
            raise ValueError('Banco deve ser SQLite ou Postgres.')

    @classmethod
    def from_env(cls):
        settings = cls(os.environ['APP_MODE'], os.environ['DATABASE_URL'],
                       os.environ['SECRET_KEY'], os.environ['OPERATOR_USERNAME'],
                       os.environ['OPERATOR_PASSWORD_HASH'])
        if settings.mode == 'cloud':
            if make_url(settings.database_url).get_backend_name() != 'postgresql':
                raise ValueError('Deploy cloud exige Postgres.')
            if os.environ.get('LAB_CONFIG'):
                raise ValueError('LAB_CONFIG não deve existir no ambiente cloud.')
        return settings
