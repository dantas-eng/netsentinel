"""REST autenticada e Observer Socket.IO; criar app não abre captura nem agente."""
from datetime import timedelta
import hmac
from secrets import token_urlsafe
from threading import RLock
from time import monotonic, time
from flask import Flask, jsonify, request, session, render_template
from flask_socketio import SocketIO
from werkzeug.security import check_password_hash
from werkzeug.exceptions import HTTPException
from sqlalchemy.exc import SQLAlchemyError
from netsentinel.api.settings import Settings
from netsentinel.events.bus import EventBus
from netsentinel.repositories.database import Database
from netsentinel.repositories.store import Repository, DomainConflict
from netsentinel.security.strategy import VictimAgentMitigationStrategy
from netsentinel.services.pipeline import BackendPipeline
from netsentinel.services.synthetic import SyntheticIdentity, SyntheticMitigation


def create_app(settings: Settings, lab_config=None, database=None, mitigation=None, clock=monotonic):
    if settings.mode == 'lab' and (lab_config is None or lab_config.hostonly_ip is None):
        raise ValueError('Backend local exige configuração do Sensor com Host-only.')
    if settings.mode == 'cloud' and (lab_config is not None or mitigation is not None):
        raise ValueError('Cloud não aceita agente/configuração do laboratório.')
    app = Flask(__name__)
    app.config.update(SECRET_KEY=settings.secret_key, MAX_CONTENT_LENGTH=8192,
                      SESSION_COOKIE_NAME='netsentinel_session',
                      SESSION_COOKIE_SECURE=False if settings.mode == 'lab' else True,
                      SESSION_COOKIE_HTTPONLY=True, SESSION_COOKIE_SAMESITE='Lax',
                      PERMANENT_SESSION_LIFETIME=timedelta(hours=1))
    socketio = SocketIO(app, async_mode='threading', manage_session=False,
                        max_http_buffer_size=8192)
    db = database or Database(settings.database_url)
    repository, bus = Repository(db), EventBus()
    identity = lab_config if settings.mode == 'lab' else SyntheticIdentity()
    strategy = (mitigation if mitigation is not None else VictimAgentMitigationStrategy(lab_config)) \
        if settings.mode == 'lab' else SyntheticMitigation(identity, clock)
    pipeline = BackendPipeline(repository, bus, identity, strategy, settings.mode)
    app.extensions.update(database=db, repository=repository, event_bus=bus,
                          pipeline=pipeline, settings=settings)
    clients, client_lock = {}, RLock()

    def authenticated():
        return (session.get('operator') == settings.operator_username and
                0 <= time() - session.get('authenticated_at', 0) < 3600)

    def disconnect_nonce(nonce):
        with client_lock:
            targets = [sid for sid, value in clients.items() if value['nonce'] == nonce]
        for sid in targets:
            socketio.server.disconnect(sid, namespace='/')

    def csrf_valid(value):
        expected = session.get('csrf')
        return isinstance(value, str) and bool(expected) and hmac.compare_digest(value, expected)

    @app.before_request
    def protect():
        if request.method in ('POST', 'PUT', 'PATCH', 'DELETE'):
            if not csrf_valid(request.headers.get('X-CSRF-Token')):
                return jsonify(error='csrf_required'), 403
        if request.path.startswith('/api/') and request.path not in (
                '/api/auth/csrf', '/api/auth/login') and not authenticated():
            return jsonify(error='authentication_required'), 401

    @app.errorhandler(HTTPException)
    def http_error(error):
        return jsonify(error=error.name), error.code

    @app.errorhandler(DomainConflict)
    def conflict(error):
        return jsonify(error=str(error)), 409

    @app.errorhandler(ValueError)
    def invalid(error):
        return jsonify(error=str(error)), 400

    @app.errorhandler(SQLAlchemyError)
    def unavailable(error):
        return jsonify(error='repository_unavailable'), 503

    @app.get('/')
    def dashboard():
        # Só o shell é público. Dados e ações continuam protegidos pela API.
        return render_template('dashboard.html')

    @app.after_request
    def response_headers(response):
        if request.path.startswith('/api/') or request.path == '/':
            response.headers['Cache-Control'] = 'no-store'
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['X-Frame-Options'] = 'DENY'
        response.headers['Content-Security-Policy'] = (
            "default-src 'self'; script-src 'self'; "
            "style-src 'self' 'unsafe-inline'; img-src 'self' data:; "
            "connect-src 'self'; font-src 'self'; object-src 'none'; "
            "base-uri 'none'; frame-ancestors 'none'; form-action 'self'"
        )
        return response

    @app.get('/health')
    def health():
        repository.latest_snapshot()  # readiness inclui existência/acesso ao schema.
        return jsonify(status='ok', mode=settings.mode)

    @app.get('/api/auth/csrf')
    def csrf():
        if 'csrf' not in session:
            session['csrf'] = token_urlsafe(32)
        return jsonify(csrf_token=session['csrf'])

    @app.post('/api/auth/login')
    def login():
        data = request.get_json()
        if not isinstance(data, dict) or set(data) != {'username', 'password'}:
            return jsonify(error='invalid_credentials'), 400
        username, password = data['username'], data['password']
        if not isinstance(username, str) or not isinstance(password, str) or len(password) > 1024:
            return jsonify(error='invalid_credentials'), 400
        valid_password = check_password_hash(settings.operator_password_hash, password)
        if not hmac.compare_digest(username.encode(), settings.operator_username.encode()) or not valid_password:
            return jsonify(error='invalid_credentials'), 401
        disconnect_nonce(session.get('nonce'))
        session.clear()
        session.permanent = True
        session.update(operator=settings.operator_username, csrf=token_urlsafe(32),
                       nonce=token_urlsafe(24), authenticated_at=time())
        return jsonify(operator=session['operator'], csrf_token=session['csrf'])

    @app.post('/api/auth/logout')
    def logout():
        disconnect_nonce(session.get('nonce'))
        session.clear()
        return jsonify(logged_out=True)

    @app.get('/api/auth/session')
    def operator_session():
        return jsonify(operator=session['operator'], mode=settings.mode)

    @app.get('/api/devices')
    def devices():
        return jsonify(devices=repository.devices())

    @app.get('/api/status')
    def status():
        runner = app.extensions.get('source_runner')
        latest = pipeline.latest
        return jsonify(mode=settings.mode, window_seconds=8,
                       source_running=bool(runner and runner.thread and runner.thread.is_alive()),
                       source_error=runner.last_error if runner else None,
                       last_snapshot_at=latest['timestamp'] if latest else None)

    @app.post('/api/devices/<mac>/reputation')
    def reputation(mac):
        data = request.get_json()
        if not isinstance(data, dict) or set(data) != {'known', 'reason'} or type(data['known']) is not bool or not isinstance(data['reason'], str):
            return jsonify(error='expected_known_and_reason'), 400
        result = repository.change_reputation(mac, data['known'], session['operator'], data['reason'])
        pipeline.publish(dict(event='reputation_changed', device=result))
        return jsonify(result)

    @app.post('/api/devices/<mac>/calibrations')
    def calibrate(mac):
        with pipeline.lock:
            latest = pipeline.latest
            if latest is None or latest['warming_up'] or latest['incomplete']:
                raise DomainConflict('Aguardar uma janela completa da fonte atual.')
            if clock() - latest['window_end_monotonic'] > 8:
                raise DomainConflict('Fonte sem snapshot recente.')
            anchor = max(clock(), latest['window_end_monotonic'])
            ident = repository.start_calibration(mac, session['operator'], latest['capture_run_id'], anchor)
        return jsonify(calibration_id=ident, status='collecting'), 202

    @app.get('/api/devices/<mac>/calibrations')
    def calibrations(mac):
        return jsonify(calibrations=repository.calibrations(mac))

    @app.get('/api/topology')
    def topology():
        latest = repository.latest_snapshot()
        return jsonify(nodes=repository.devices(), links=latest['links'] if latest else [],
                       timestamp=latest['timestamp'] if latest else None,
                       source='live' if settings.mode == 'lab' else 'synthetic')

    @app.get('/api/events')
    def events():
        after_id, limit = int(request.args.get('after_id', 0)), int(request.args.get('limit', 100))
        if after_id < 0 or not 1 <= limit <= 500:
            raise ValueError('Paginação inválida.')
        return jsonify(events=repository.events(after_id, limit))

    @app.get('/api/devices/<mac>/history')
    def device_history(mac):
        limit = int(request.args.get('limit', 100))
        if not 1 <= limit <= 500:
            raise ValueError('Paginação inválida.')
        return jsonify(history=repository.risk_history(mac, limit))

    @app.get('/api/audit')
    def audits():
        return jsonify(audit=repository.audits())

    @socketio.on('connect')
    def socket_connect(auth):
        if not authenticated() or not isinstance(auth, dict) or not csrf_valid(auth.get('csrf_token')):
            return False
        with client_lock:
            clients[request.sid] = dict(nonce=session['nonce'], expires=session['authenticated_at'] + 3600)

    @socketio.on('disconnect')
    def socket_disconnect(reason=None):
        with client_lock:
            clients.pop(request.sid, None)

    # Somente conexões autenticadas entram; nenhum handler de mutação por WebSocket.
    def notify(event):
        with client_lock:
            targets = tuple(clients.items())
        for sid, value in targets:
            if time() >= value['expires']:
                socketio.server.disconnect(sid, namespace='/')
            else:
                socketio.emit(event['event'], event, to=sid)

    bus.subscribe(notify)
    return app
