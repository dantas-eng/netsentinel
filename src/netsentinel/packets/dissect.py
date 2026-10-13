"""Dissecação de quadros ARP Ethernet/IPv4 com o intervalo de bytes de cada campo.

O frontend só desenha o resultado; o veredito usa o mesmo inventário do detector.
"""
import struct

MAX_FRAME_BYTES = 128
ETHERTYPE_ARP, ETHERTYPE_VLAN = 0x0806, 0x8100


def _mac(raw, at):
    return ':'.join(f'{b:02x}' for b in raw[at:at + 6])


def _ip(raw, at):
    return '.'.join(str(b) for b in raw[at:at + 4])


def _field(name, value, start, end):
    return dict(name=name, value=value, start=start, end=end)


def dissect(raw: bytes) -> dict:
    if len(raw) < 14:
        raise ValueError('Quadro menor que o cabeçalho Ethernet.')
    eth_dst, eth_src = _mac(raw, 0), _mac(raw, 6)
    layers = [dict(name='Ethernet II', fields=[_field('Destino', eth_dst, 0, 6),
                                                _field('Origem', eth_src, 6, 12)])]
    at = 12
    ethertype = struct.unpack_from('!H', raw, at)[0]
    if ethertype == ETHERTYPE_VLAN:
        if len(raw) < 18:
            raise ValueError('Tag 802.1Q incompleta.')
        tci = struct.unpack_from('!H', raw, at + 2)[0]
        layers[0]['fields'].append(_field('Tipo', '802.1Q (0x8100)', at, at + 2))
        layers.append(dict(name='802.1Q', fields=[_field('Prioridade', str(tci >> 13), at + 2, at + 4),
                                                   _field('VLAN', str(tci & 0x0fff), at + 2, at + 4)]))
        at += 4
        ethertype = struct.unpack_from('!H', raw, at)[0]
        type_field = _field('Tipo', 'ARP (0x0806)', at, at + 2)
        layers[1]['fields'].append(type_field)
    else:
        layers[0]['fields'].append(_field('Tipo', 'ARP (0x0806)', at, at + 2))
    if ethertype != ETHERTYPE_ARP:
        raise ValueError('EtherType não é ARP.')
    base = at + 2
    if len(raw) < base + 28:
        raise ValueError('ARP incompleto.')
    htype, ptype, hlen, plen, opcode = struct.unpack_from('!HHBBH', raw, base)
    if (htype, ptype, hlen, plen) != (1, 0x0800, 6, 4):
        raise ValueError('ARP não é Ethernet/IPv4.')
    sender_mac, sender_ip = _mac(raw, base + 8), _ip(raw, base + 14)
    target_mac, target_ip = _mac(raw, base + 18), _ip(raw, base + 24)
    kind = {1: 'request', 2: 'reply'}.get(opcode, f'opcode {opcode}')
    layers.append(dict(name=f'Address Resolution Protocol ({kind})', fields=[
        _field('Tipo de hardware', 'Ethernet (1)', base, base + 2),
        _field('Tipo de protocolo', 'IPv4 (0x0800)', base + 2, base + 4),
        _field('Tamanho do endereço físico', '6', base + 4, base + 5),
        _field('Tamanho do endereço lógico', '4', base + 5, base + 6),
        _field('Opcode', f'{kind} ({opcode})', base + 6, base + 8),
        _field('MAC do remetente', sender_mac, base + 8, base + 14),
        _field('IP do remetente', sender_ip, base + 14, base + 18),
        _field('MAC do alvo', target_mac, base + 18, base + 24),
        _field('IP do alvo', target_ip, base + 24, base + 28)]))
    end = base + 28
    if len(raw) > end:
        layers.append(dict(name='Preenchimento', fields=[
            _field('Bytes após o ARP', f'{len(raw) - end} bytes', end, len(raw))]))
    summary = (f'Quem tem {target_ip}? Diga a {sender_ip}' if opcode == 1
               else f'{sender_ip} está em {sender_mac}')
    return dict(layers=layers, summary=summary, opcode=opcode, eth_src=eth_src, eth_dst=eth_dst,
                sender_mac=sender_mac, sender_ip=sender_ip, target_mac=target_mac,
                target_ip=target_ip, length=len(raw))


def verdict(packet: dict, trusted: dict) -> dict:
    ip = packet['sender_ip']
    if ip == '0.0.0.0':
        return dict(spoofed=False, expected_mac=None, reason='probe')
    expected = trusted.get(ip)
    if expected is None:
        return dict(spoofed=False, expected_mac=None, reason='ip_not_in_inventory')
    if packet['sender_mac'] != expected.lower():
        return dict(spoofed=True, expected_mac=expected, reason='spoofed_trusted_ip')
    return dict(spoofed=False, expected_mac=expected, reason='matches_inventory')
