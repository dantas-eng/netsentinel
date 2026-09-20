"""Configuração local confiável; nenhum destino é aprendido pelo tráfego."""
from dataclasses import dataclass, asdict
from ipaddress import IPv4Address, IPv4Network
from pathlib import Path
import hashlib
import json
import re


def validate_mac(value):
    if not isinstance(value, str) or not re.fullmatch(r"[0-9a-fA-F]{2}(?::[0-9a-fA-F]{2}){5}", value):
        raise ValueError("MAC inválido: esperado xx:xx:xx:xx:xx:xx.")
    value = value.lower()
    if int(value[:2], 16) & 1 or value == "00:00:00:00:00:00":
        raise ValueError("MAC deve ser unicast e não nulo.")
    return value


def validate_interface(value):
    if not isinstance(value, str) or not re.fullmatch(r"[A-Za-z0-9_.-]{1,15}", value) or value == "lo":
        raise ValueError("Interface inválida.")
    return value


@dataclass(frozen=True)
class LabConfig:
    interface: str
    internal_cidr: str
    victim_ip: str
    victim_mac: str
    gateway_ip: str
    gateway_mac: str
    attacker_ip: str
    attacker_mac: str
    sensor_internal_ip: str
    sensor_internal_mac: str
    agent_port: int
    token_file: str
    state_dir: str
    isolated_lab: bool
    hostonly_interface: str | None = None
    hostonly_ip: str | None = None
    hostonly_cidr: str | None = None

    def __post_init__(self):
        validate_interface(self.interface)
        if self.isolated_lab is not True:
            raise ValueError("Exige laboratório isolado explicitamente configurado.")
        network = IPv4Network(self.internal_cidr)
        private = [IPv4Network(cidr) for cidr in ('10.0.0.0/8', '172.16.0.0/12', '192.168.0.0/16')]
        if not any(network.subnet_of(block) for block in private):
            raise ValueError("A rede interna deve pertencer a RFC1918.")
        ips, macs = [], []
        for role in ('victim', 'gateway', 'attacker', 'sensor_internal'):
            ip = IPv4Address(getattr(self, role + '_ip'))
            if ip not in network or ip in (network.network_address, network.broadcast_address):
                raise ValueError("Todos os nós devem ser hosts da Internal Network.")
            ips.append(ip)
            name = role + '_mac'
            mac = validate_mac(getattr(self, name))
            object.__setattr__(self, name, mac)
            macs.append(mac)
        if len(set(ips)) != 4 or len(set(macs)) != 4:
            raise ValueError("Os quatro nós devem ter IPs e MACs distintos.")
        if type(self.agent_port) is not int or not 1024 <= self.agent_port <= 65535:
            raise ValueError("Porta inválida.")
        if not Path(self.token_file).is_absolute() or not Path(self.state_dir).is_absolute():
            raise ValueError("Token e estado exigem caminhos absolutos locais.")
        host = (self.hostonly_interface, self.hostonly_ip, self.hostonly_cidr)
        if any(v is not None for v in host):
            if not all(v is not None for v in host):
                raise ValueError("Configure interface, IP e CIDR Host-only juntos.")
            validate_interface(self.hostonly_interface)
            hostnet = IPv4Network(self.hostonly_cidr)
            hostip = IPv4Address(self.hostonly_ip)
            if self.hostonly_interface == self.interface or hostnet.overlaps(network):
                raise ValueError("Host-only deve ser separada da Internal Network.")
            if not any(hostnet.subnet_of(block) for block in private):
                raise ValueError("Host-only deve pertencer a RFC1918.")
            if hostip not in hostnet or hostip in (hostnet.network_address, hostnet.broadcast_address):
                raise ValueError("IP Host-only inválido.")

    def fingerprint(self):
        return hashlib.sha256(json.dumps(asdict(self), sort_keys=True).encode()).hexdigest()

    def trusted_bindings(self):
        return {self.victim_ip: self.victim_mac, self.gateway_ip: self.gateway_mac,
                self.attacker_ip: self.attacker_mac, self.sensor_internal_ip: self.sensor_internal_mac}

    def require_attacker(self, mac):
        mac = validate_mac(mac)
        if mac != self.attacker_mac:
            raise ValueError("Somente o MAC do Atacante configurado pode ser bloqueado.")
        return mac


def load_config(path):
    return LabConfig(**json.loads(Path(path).read_text()))


def load_token(path):
    token = Path(path).read_text().strip()
    if not re.fullmatch(r"[0-9a-fA-F]{64}", token):
        raise ValueError("O token deve conter 64 caracteres hexadecimais aleatórios.")
    return token
