"""Comandos locais fixos com argv separado, sem shell e com timeout."""
import json
import subprocess
import shutil
from pathlib import Path


class SystemFailure(RuntimeError):
    pass


class LinuxSystem:
    def run(self, argv, stdin=None):
        if argv[0] not in ('ip', 'nft'):
            raise ValueError("Executável não permitido.")
        executable = shutil.which(argv[0], path='/usr/sbin:/usr/bin:/sbin:/bin')
        if executable is None:
            raise SystemFailure(f"Executável ausente: {argv[0]}")
        try:
            result = subprocess.run([executable, *argv[1:]], input=stdin,
                                    capture_output=True, text=True, timeout=5, check=True)
        except (OSError, subprocess.SubprocessError) as exc:
            # Não devolver stderr, paths ou conteúdo de comandos pela API.
            raise SystemFailure(f"Falha na ação local {argv[0]}.") from exc
        return result.stdout

    def json(self, argv):
        try:
            return json.loads(self.run(argv))
        except json.JSONDecodeError as exc:
            raise SystemFailure("Resposta inválida da ferramenta local.") from exc

    def sysctl(self, path):
        return Path('/proc/sys/' + path).read_text().strip()


def preflight(config, role, system):
    """Não pode comprovar o modo VirtualBox; verifica condições visíveis na VM."""
    if role not in ('victim', 'attacker', 'sensor'):
        raise ValueError("Papel inválido.")
    allowed = {config.interface}
    if role == 'sensor':
        if not config.hostonly_interface:
            raise ValueError("Sensor exige configuração Host-only explícita.")
        allowed.add(config.hostonly_interface)
    links = system.json(['ip', '-j', 'address', 'show'])
    by_name = {link['ifname']: link for link in links}
    for interface in allowed:
        if interface not in by_name:
            raise SystemFailure("Interface configurada não existe.")
    for link in links:
        if link['ifname'] == 'lo':
            continue
        if link['ifname'] not in allowed:
            raise SystemFailure("Interface adicional fora da topologia aprovada.")
        if link.get('master') or link.get('linkinfo', {}).get('info_kind') in ('bridge', 'bond'):
            raise SystemFailure("Bridge/bond não permitido no laboratório.")
    internal = by_name[config.interface]
    prefix = 'sensor_internal' if role == 'sensor' else role
    addresses = {a['local'] for a in internal.get('addr_info', []) if a['family'] == 'inet'}
    if addresses != {getattr(config, prefix + '_ip')}:
        raise SystemFailure("IP interno não corresponde ao papel configurado.")
    if internal.get('address', '').lower() != getattr(config, prefix + '_mac'):
        raise SystemFailure("MAC da interface não corresponde ao nó configurado.")
    if role == 'sensor':
        addresses = {a['local'] for a in by_name[config.hostonly_interface].get('addr_info', [])
                     if a['family'] == 'inet'}
        if addresses != {config.hostonly_ip}:
            raise SystemFailure("IP Host-only não corresponde à configuração.")
    for family in ('-4', '-6'):
        if any(route.get('dst') == 'default' for route in
               system.json(['ip', family, '-j', 'route', 'show', 'table', 'all'])):
            raise SystemFailure("Rota default proibida no laboratório.")
    if system.sysctl('net/ipv4/ip_forward') != '0':
        raise SystemFailure("IPv4 forwarding deve estar desativado.")
    for interface in allowed | {'all'}:
        for family in ('ipv4', 'ipv6'):
            if system.sysctl(f'net/{family}/conf/{interface}/forwarding') != '0':
                raise SystemFailure("Encaminhamento entre interfaces deve estar desativado.")
