"""Migrações online e geração de SQL offline para os dois dialetos."""
import os
from alembic import context
from sqlalchemy import create_engine
from netsentinel.repositories.models import Base

config = context.config
metadata = Base.metadata


def run(connection):
    context.configure(connection=connection, target_metadata=metadata, render_as_batch=True)
    with context.begin_transaction():
        context.run_migrations()


if context.is_offline_mode():
    context.configure(url=config.get_main_option('sqlalchemy.url') or os.environ['DATABASE_URL'],
                      target_metadata=metadata, literal_binds=True, render_as_batch=True)
    with context.begin_transaction():
        context.run_migrations()
else:
    supplied = config.attributes.get('connection')
    if supplied is not None:
        run(supplied)
    else:
        engine = create_engine(os.environ['DATABASE_URL'])
        with engine.begin() as connection:
            run(connection)
        engine.dispose()
