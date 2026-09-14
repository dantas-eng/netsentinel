"""Serviço dedicado na Vítima e restauração local com exclusão mútua."""
import argparse
import fcntl
import json
from pathlib import Path
from wsgiref.simple_server import make_server, WSGIRequestHandler
from netsentinel.security.config import load_config, load_token
from netsentinel.security.system import LinuxSystem
from netsentinel.security.agent.api import create_app
from netsentinel.security.agent.controller import VictimController


class BoundedHandler(WSGIRequestHandler):
    def setup(self):
        self.request.settimeout(5)
        super().setup()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('serve', 'prepare', 'status', 'restore'))
    parser.add_argument('--config', required=True)
    args = parser.parse_args()
    config = load_config(args.config)
    Path(config.state_dir).mkdir(parents=True, exist_ok=True)
    # Mesmo lock para CLI e servidor. Não restaurar enquanto o agente está ativo.
    with (Path(config.state_dir) / 'agent.lock').open('a') as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            parser.error('Pare o serviço antes de executar ações locais.')
        controller = VictimController(config, LinuxSystem())
        if args.action == 'serve':
            token = load_token(config.token_file)
            controller.prepare()
            app = create_app(config, controller, token)
            # Servidor WSGI simples e serial para esta API de laboratório; sem debug/reloader.
            with make_server(config.victim_ip, config.agent_port, app,
                             handler_class=BoundedHandler) as server:
                server.serve_forever()
        else:
            print(json.dumps(getattr(controller, args.action)(), ensure_ascii=False))


if __name__ == '__main__':
    main()
