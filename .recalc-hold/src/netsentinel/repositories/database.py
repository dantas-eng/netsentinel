"""Uma Session por operação; engine compartilhado e escrita serial no MVP."""
from contextlib import contextmanager
from threading import RLock
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool


class Database:
    def __init__(self, url):
        kwargs = {'pool_pre_ping': True}
        if url.startswith('sqlite:'):
            kwargs['connect_args'] = {'check_same_thread': False, 'timeout': 15}
            if ':memory:' in url or url == 'sqlite://':
                kwargs['poolclass'] = StaticPool
        self.engine = create_engine(url, **kwargs)
        if self.engine.dialect.name == 'sqlite':
            @event.listens_for(self.engine, 'connect')
            def foreign_keys(connection, _):
                cursor = connection.cursor()
                cursor.execute('PRAGMA foreign_keys=ON')
                cursor.close()
        self.sessions = sessionmaker(self.engine, expire_on_commit=False)
        self.lock = RLock()

    @contextmanager
    def transaction(self):
        # MVP opera em um único processo. Não compartilhar Session entre threads.
        with self.lock, self.sessions.begin() as session:
            yield session
