"""API HTTP do laboratório: duas ações fixas; restauração não é exposta."""
import hmac
from flask import Flask, jsonify, request
from werkzeug.exceptions import HTTPException
from netsentinel.security.system import SystemFailure


def create_app(config, controller, token):
    app = Flask(__name__)
    app.config['MAX_CONTENT_LENGTH'] = 512

    @app.before_request
    def authenticate():
        # Sem ProxyFix e sem confiar em X-Forwarded-For: exige o peer TCP interno.
        if request.remote_addr != config.sensor_internal_ip:
            return jsonify(error='forbidden_source'), 403
        supplied = request.headers.get('Authorization', '')
        if not hmac.compare_digest(supplied.encode(), ('Bearer ' + token).encode()):
            return jsonify(error='unauthorized'), 401

    @app.errorhandler(HTTPException)
    def http_error(error):
        return jsonify(error=error.name), error.code

    @app.errorhandler(SystemFailure)
    @app.errorhandler(OSError)
    @app.errorhandler(ValueError)
    def system_error(error):
        # O cliente consulta status após falhas; não presumir rollback das duas camadas.
        return jsonify(error='local_action_failed', status_required=True), 503

    @app.get('/v1/status')
    def status():
        return jsonify(controller.status())

    @app.post('/v1/mitigations')
    def apply():
        data = request.get_json()
        if not isinstance(data, dict) or set(data) != {'attacker_mac'}:
            return jsonify(error='expected_attacker_mac_only'), 400
        try:
            mac = config.require_attacker(data['attacker_mac'])
        except ValueError:
            return jsonify(error='invalid_or_unapproved_mac'), 400
        return jsonify(controller.apply(mac))

    return app
