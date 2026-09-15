"""Migração, bootstrap explícito, poda manual e servidor local. Cloud usa a factory WSGI."""
import argparse
import os
from netsentinel.api.settings import Settings
from netsentinel.api.app import create_app
from netsentinel.repositories.database import Database
from netsentinel.repositories.migrate import upgrade_schema
from netsentinel.repositories.store import Repository
from netsentinel.security.config import load_config
from netsentinel.services.runner import SourceRunner
from netsentinel.services.synthetic import SyntheticIdentity


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='action', required=True)
    sub.add_parser('migrate')
    sub.add_parser('bootstrap')
    sub.add_parser('serve')
    prune = sub.add_parser('prune')
    prune.add_argument('--keep-days', dest='keep_days', type=int, default=None)
    prune.add_argument('--confirm', action='store_true')
    args = parser.parse_args()
    if args.action == 'prune':
        if args.keep_days is None:
            parser.error('--keep-days é obrigatório')
        url = os.environ['DATABASE_URL']
        if url.startswith('postgresql://'):
            url = url.replace('postgresql://', 'postgresql+psycopg://', 1)
        db = Database(url)
        try:
            result = Repository(db).prune_events(
                args.keep_days, os.environ.get('OPERATOR_USERNAME', 'operator'), args.confirm)
            print(result)
        finally:
            db.engine.dispose()
        return
    if args.action == 'migrate':
        url = os.environ['DATABASE_URL']
        if url.startswith('postgresql://'):
            url = url.replace('postgresql://', 'postgresql+psycopg://', 1)
        db = Database(url)
        try:
            upgrade_schema(db.engine)
        finally:
            db.engine.dispose()
        return
    settings = Settings.from_env()
    lab = load_config(os.environ['LAB_CONFIG']) if settings.mode == 'lab' else None
    app = create_app(settings, lab)
    if args.action == 'bootstrap':
        identity = lab or SyntheticIdentity()
        app.extensions['repository'].bootstrap(
            [identity.gateway_mac, identity.victim_mac, identity.sensor_internal_mac],
            settings.operator_username)
        return
    if settings.mode != 'lab':
        parser.error('Use Gunicorn com netsentinel.api.wsgi:create_service() para cloud.')
    runner = SourceRunner(app, lab, int(os.environ['LAB_MAX_OBSERVATIONS']))
    runner.start()
    try:
        app.extensions['socketio'].run(app, host=lab.hostonly_ip,
            port=int(os.environ.get('PORT', '8080')), debug=False,
            use_reloader=False, allow_unsafe_werkzeug=True)
    finally:
        runner.stop()
        app.extensions['database'].engine.dispose()


if __name__ == '__main__':
    main()
