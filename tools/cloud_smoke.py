"""Verificação HTTPS autenticada; não aplica mitigação nem altera dispositivos.

CookieJar respeita Secure; login faz CSRF-first. Não imprime cookies, senhas,
token CSRF ou corpos de resposta. Socket.IO/browser são validados manualmente.
"""
from getpass import getpass
from http.cookiejar import CookieJar
import json
import os
import time
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import HTTPCookieProcessor, HTTPRedirectHandler, Request, build_opener


def validate_url(url):
    parts = urlsplit(url)
    if (parts.scheme != 'https' or not parts.hostname or parts.username or parts.password
            or parts.query or parts.fragment or parts.path not in ('', '/')):
        raise ValueError('CLOUD_URL deve ser uma origem HTTPS, sem caminho ou credenciais.')
    return url.rstrip('/')


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None  # Credencial do operador só vai à origem configurada.


class CloudClient:
    def __init__(self, url):
        self.url = validate_url(url)
        self.cookies = CookieJar()
        self.opener = build_opener(NoRedirect(), HTTPCookieProcessor(self.cookies))

    def __call__(self, path, data=None, csrf=None):
        headers = {'Accept': 'application/json'}
        if data is not None:
            headers['Content-Type'] = 'application/json'
        if csrf:
            headers['X-CSRF-Token'] = csrf
        request = Request(self.url + path, headers=headers,
                          data=json.dumps(data).encode() if data is not None else None)
        try:
            with self.opener.open(request, timeout=30) as response:
                return response.status, json.load(response)
        except HTTPError as error:
            return error.code, {}  # Não imprimir páginas de erro ou segredos.
        except (URLError, TimeoutError, ValueError):
            raise RuntimeError('Falha de conexão HTTPS ou resposta não JSON.') from None


def check(client, username, password, *, sleep=time.sleep):
    def expect(path, status=200, data=None, csrf=None):
        actual, body = client(path, data, csrf)
        if actual != status:
            raise RuntimeError(f'Verificação falhou em {path}: HTTP {actual}, esperado {status}.')
        return body

    health = expect('/health')
    if health.get('status') != 'ok' or health.get('mode') != 'cloud':
        raise RuntimeError('Health não confirma ambiente cloud.')
    expect('/api/devices', 401)
    token = expect('/api/auth/csrf')['csrf_token']
    expect('/api/auth/login', 403, {})
    session = expect('/api/auth/login', data={'username': username, 'password': password}, csrf=token)
    try:
        for path in ('topology', 'devices', 'audit'):
            expect('/api/' + path)
        first = expect('/api/status')
        sleep(3)
        second = expect('/api/status')
        if (second.get('mode') != 'cloud' or not second.get('source_running')
                or second.get('source_error') or not first.get('last_snapshot_at')
                or (second.get('last_snapshot_at') or 0) <= first['last_snapshot_at']):
            raise RuntimeError('Fonte sintética não está saudável/avançando.')
        events = expect('/api/events').get('events', [])
        if not events or any(event.get('source') != 'synthetic' for event in events):
            raise RuntimeError('Eventos ausentes ou origem diferente de synthetic.')
    finally:
        expect('/api/auth/logout', data={}, csrf=session['csrf_token'])
    expect('/api/devices', 401)


def main():
    try:
        url = validate_url(os.environ['CLOUD_URL'])
        username = os.environ.get('CLOUD_OPERATOR_USERNAME', 'operador')
        password = os.environ.get('CLOUD_OPERATOR_PASSWORD') or getpass('Senha do operador cloud: ')
        check(CloudClient(url), username, password)
    except (KeyError, ValueError, RuntimeError) as error:
        raise SystemExit(str(error)) from None
    print('HTTPS, CSRF/sessão, REST e fonte sintética avançando: OK.')


if __name__ == '__main__':
    main()
