"""CD do SHA aprovado: nunca imprimir token ou resposta bruta do provedor.

Não provisiona serviços nem altera plano. O serviço Free deve existir conforme
render.yaml. Falhas de POST não são repetidas: a primeira chamada pode já ter
criado um deploy. Verificar o painel antes de reexecutar o workflow.
"""
import json
import os
from pathlib import Path
import re
import time
from urllib.error import HTTPError, URLError
from urllib.request import HTTPRedirectHandler, Request, build_opener


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None  # Não reenviar Authorization para outro destino.


class RenderAPI:
    def __init__(self, token):
        self.token = token
        self.opener = build_opener(NoRedirect())

    def __call__(self, path, data=None):
        request = Request('https://api.render.com/v1' + path,
                          data=json.dumps(data).encode() if data is not None else None,
                          headers={'Authorization': 'Bearer ' + self.token,
                                   'Accept': 'application/json',
                                   'Content-Type': 'application/json'})
        try:
            with self.opener.open(request, timeout=30) as response:
                return json.load(response)
        except HTTPError as error:
            raise RuntimeError(f'Render respondeu HTTP {error.code}; consulte o painel.') from None
        except (URLError, TimeoutError, ValueError):
            raise RuntimeError('Render indisponível ou resposta inválida; consulte o painel.') from None


def deploy(api, service_id, sha, *, clock=time.monotonic, sleep=time.sleep, timeout=1200):
    if not re.fullmatch(r'srv-[a-z0-9]+', service_id):
        raise ValueError('RENDER_SERVICE_ID inválido.')
    if not re.fullmatch(r'[a-f0-9]{40}', sha):
        raise ValueError('DEPLOY_SHA deve ser um commit Git completo.')
    path = f'/services/{service_id}/deploys'
    result = api(path, {'commitId': sha, 'clearCache': 'do_not_clear'})
    ident = result.get('id', '')
    if not re.fullmatch(r'dep-[a-z0-9]+', ident):
        raise RuntimeError('Render não retornou um identificador de deploy válido.')
    deadline = clock() + timeout
    while clock() < deadline:
        result = api(f'{path}/{ident}')
        status = result.get('status')
        if status == 'live':
            if result.get('commit', {}).get('id') != sha:
                raise RuntimeError('Commit publicado difere do commit aprovado na CI.')
            return {'deploy_id': ident, 'commit': sha, 'status': 'live'}
        if status not in {'created', 'queued', 'build_in_progress',
                          'pre_deploy_in_progress', 'update_in_progress'}:
            raise RuntimeError('Deploy falhou, foi cancelado ou tem status não reconhecido.')
        sleep(10)
    raise RuntimeError('Tempo limite do deploy; verificar o painel antes de tentar novamente.')


def main():
    try:
        result = deploy(RenderAPI(os.environ['RENDER_API_KEY']),
                        os.environ['RENDER_SERVICE_ID'], os.environ['DEPLOY_SHA'])
    except (KeyError, ValueError, RuntimeError) as error:
        raise SystemExit(str(error)) from None
    # Só metadados públicos, para anexar como evidência do commit implantado.
    Path('deploy-evidence.json').write_text(json.dumps(result, indent=2) + '\n')
    print('Deploy live confirmado para o SHA aprovado; iniciando verificação HTTPS.')


if __name__ == '__main__':
    main()
