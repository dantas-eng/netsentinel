"""Strategy HTTP restrita ao IP interno da Vítima, sem proxies ou redirects."""
from http.client import HTTPConnection, HTTPException
from math import isfinite
import json
from typing import Protocol
from netsentinel.security.config import load_token


class MitigationStrategy(Protocol):
    def apply(self, attacker_mac: str) -> dict: ...
    def status(self) -> dict: ...


class AgentFailure(RuntimeError):
    pass


class DirectAgentTransport:
    def __init__(self, config, timeout=5.0):
        if not isfinite(timeout) or not 0 < timeout <= 30:
            raise ValueError('Timeout deve ser positivo e limitado.')
        self.config, self.timeout = config, timeout

    def request(self, method, path, payload=None):
        token = load_token(self.config.token_file)
        connection = HTTPConnection(self.config.victim_ip, self.config.agent_port,
                                    timeout=self.timeout,
                                    source_address=(self.config.sensor_internal_ip, 0))
        try:
            body = json.dumps(payload) if payload is not None else None
            connection.request(method, path, body=body,
                               headers={'Authorization': 'Bearer ' + token,
                                        'Content-Type': 'application/json'})
            response = connection.getresponse()
            raw = response.read(65537)
            if response.status != 200 or len(raw) > 65536:
                raise AgentFailure('Agente recusou a operação ou retornou resposta inválida.')
            value = json.loads(raw)
            if not isinstance(value, dict):
                raise AgentFailure('Resposta JSON inesperada.')
            return value
        except (OSError, ValueError, HTTPException) as exc:
            raise AgentFailure('Falha de comunicação com o agente.') from exc
        finally:
            connection.close()


class VictimAgentMitigationStrategy:
    def __init__(self, config, transport=None):
        self.config = config
        self.transport = transport if transport is not None else DirectAgentTransport(config)

    def apply(self, attacker_mac):
        mac = self.config.require_attacker(attacker_mac)
        result = self.transport.request('POST', '/v1/mitigations', {'attacker_mac': mac})
        if (result.get('attacker_mac') != mac or result.get('mitigated') is not True
                or result.get('blocked') is not True or result.get('arp_static_correct') is not True
                or result.get('gateway_ip') != self.config.gateway_ip):
            raise AgentFailure('Mitigação não confirmada pelo agente.')
        return result

    def status(self):
        return self.transport.request('GET', '/v1/status')
