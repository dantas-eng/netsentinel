"""Executar explicitamente antes do servidor; não criar schema por create_all."""
from pathlib import Path
from alembic import command
from alembic.config import Config


def migration_config():
    root = Path(__file__).resolve().parents[3]
    config = Config(str(root / 'alembic.ini'))
    config.set_main_option('script_location', str(root / 'migrations'))
    return config


def upgrade_schema(engine):
    config = migration_config()
    with engine.begin() as connection:
        config.attributes['connection'] = connection
        command.upgrade(config, 'head')
