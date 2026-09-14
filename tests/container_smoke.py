"""Smoke HTTP do Compose sintético; executar com .env.docker de CI gerado pelo job.

Usa conexão real com localhost, mas não simula a política de cookies do navegador.
O cliente envia explicitamente o cookie recebido para testar o fluxo CSRF/sessão.
"""
from http.client import HTTPConnection
from http.cookies import SimpleCookie
import json
from pathlib import Path


def main():
    values = dict(line.split('=', 1) for line in Path('.env.docker').read_text().splitlines()
                  if line and not line.startswith('#'))
    password = values['SYNTHETIC_OPERATOR_PASSWORD']  # Somente ambiente efêmero de CI.
    connection = HTTPConnection('localhost', 8080, timeout=10)
    cookie = ''

    def request(method, path, data=None, csrf=None):
        nonlocal cookie
        headers = {'Accept': 'application/json'}
        if cookie:
            headers['Cookie'] = cookie
        if csrf:
            headers['X-CSRF-Token'] = csrf
        if data is not None:
            headers['Content-Type'] = 'application/json'
        connection.request(method, path, body=json.dumps(data) if data is not None else None,
                           headers=headers)
        response = connection.getresponse()
        if response.getheader('Set-Cookie'):
            parsed = SimpleCookie(response.getheader('Set-Cookie'))
            cookie = '; '.join(f'{key}={value.value}' for key, value in parsed.items())
        return response.status, json.loads(response.read())

    try:
        assert request('GET', '/api/devices')[0] == 401
        status, result = request('GET', '/api/auth/csrf')
        assert status == 200
        assert request('POST', '/api/auth/login', {})[0] == 403
        status, session = request('POST', '/api/auth/login',
                                  {'username': 'operador', 'password': password}, result['csrf_token'])
        assert status == 200
        for path in ('topology', 'devices', 'events', 'audit', 'status'):
            status, data = request('GET', '/api/' + path)
            assert status == 200, path
            if path == 'events':
                assert data['events'] and all(e['source'] == 'synthetic' for e in data['events'])
            if path == 'status':
                assert data['mode'] == 'cloud' and data['source_running']
        assert request('POST', '/api/auth/logout', csrf=session['csrf_token'])[0] == 200
        assert request('GET', '/api/devices')[0] == 401
        print('Compose: migração, fonte sintética, REST e CSRF/sessão confirmados por HTTP.')
    finally:
        connection.close()


if __name__ == '__main__':
    main()
