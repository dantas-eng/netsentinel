"""Tabela exclusiva; dados interpolados são validados antes de chegar ao nft."""
from netsentinel.security.config import validate_interface, validate_mac

TABLE = 'netsentinel_lab'


def ruleset(interface, attacker_mac, backend_ip, port, marker):
    interface = validate_interface(interface)
    mac = validate_mac(attacker_mac)
    # Outros argumentos vêm exclusivamente de LabConfig/UUID, nunca do JSON HTTP.
    return f'''create table netdev {TABLE} {{ comment "{marker}"; }}
add counter netdev {TABLE} seen
add counter netdev {TABLE} dropped
add counter netdev {TABLE} passed
add set netdev {TABLE} blocked {{ type ether_addr; }}
add chain netdev {TABLE} guard {{ type filter hook ingress device "{interface}" priority -500; policy accept; }}
add rule netdev {TABLE} guard ether saddr {mac} counter name seen
add rule netdev {TABLE} guard ether saddr @blocked counter name dropped drop
add rule netdev {TABLE} guard ip saddr != {backend_ip} tcp dport {port} drop
add chain netdev {TABLE} after_guard {{ type filter hook ingress device "{interface}" priority -490; policy accept; }}
add rule netdev {TABLE} after_guard ether saddr {mac} counter name passed
'''


def block(mac):
    mac = validate_mac(mac)
    # Flush+add em um único batch: idempotente, sem zerar os contadores.
    return (f'flush set netdev {TABLE} blocked\n'
            f'add element netdev {TABLE} blocked {{ {mac} }}\n')
