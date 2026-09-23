"""Dataset inteiramente sintético: PCAP → captura real → features reais.

Não abre interfaces nem transmite pacotes. Histórico e reputação são contexto
sintético explícito anterior à janela, não estimativas obtidas do rótulo.
"""
import hashlib
import io
import json
import random
from dataclasses import asdict
from pathlib import Path
from unittest.mock import patch

from scapy.config import conf

from netsentinel.analysis.contracts import Reputation
from netsentinel.analysis.models import RiskInputs

TARGET = '02:00:00:00:00:30'
GATEWAY = '02:00:00:00:00:10'
VICTIM = '02:00:00:00:00:20'
SEED = 20260919
DATASET_VERSION = 2
FAMILIES = [('normal', 0, 70), ('burst', 0, 70), ('new_device', 0, 70),
            ('discovery', 0, 70), ('migration_ambiguous', 0, 70),
            ('unknown_history', 0, 70), ('poison_fast', 1, 60),
            ('poison_slow', 1, 60), ('poison_no_gateway_claim', 1, 60)]


class Context:
    def __init__(self, reputation, baseline):
        self.reputation, self.baseline = reputation, baseline

    def get_reputation(self, mac):
        return self.reputation if mac == TARGET else Reputation.KNOWN

    def get_baseline_bps(self, mac):
        return self.baseline if mac == TARGET else None


def scenario(family, rng, ratio_rng):
    """Perfil por família; NEW/KNOWN e histórico variam também nos ataques."""
    known = rng.random() < 0.55
    reputation = Reputation.KNOWN if known else Reputation.NEW
    baseline = rng.uniform(100, 700) if known else None
    frequency = rng.uniform(0.125, 1.5)
    conflict = False
    payload_count = rng.randint(2, 8)
    if family == 'burst':
        payload_count = rng.randint(30, 80)
    elif family == 'new_device':
        reputation, baseline = Reputation.NEW, None
    elif family == 'discovery':
        frequency = rng.uniform(2, 8)
    elif family == 'migration_ambiguous':
        conflict, frequency = True, rng.uniform(0.125, 4)
    elif family == 'unknown_history':
        reputation, baseline = Reputation.UNKNOWN, None
    elif family.startswith('poison'):
        frequency = rng.uniform(3, 16) if family == 'poison_fast' else rng.uniform(0.25, 6)
        conflict = family != 'poison_no_gateway_claim'
    config = {'reputation': reputation.value, 'baseline_bps': baseline,
              'arp_count': max(1, round(frequency * 8)), 'gateway_claim': conflict,
              'payload_count': payload_count, 'payload_size': rng.randint(64, 1000)}
    # RNG separado conserva parâmetros anteriores e split, sem consultar score/rótulo.
    # Faixas sobrepostas: ratio não deve ser um codificador perfeito do rótulo.
    ranges = {'normal': (0., .8), 'burst': (0., .8), 'new_device': (0., .8),
              'discovery': (0., .6), 'migration_ambiguous': (.1, 1.),
              'unknown_history': (0., 1.), 'poison_fast': (.25, 1.),
              'poison_slow': (.25, 1.), 'poison_no_gateway_claim': (.25, 1.)}
    fraction = ratio_rng.uniform(*ranges[family])
    replies = round(config['arp_count'] * fraction)
    # Cenários de envenenamento/migração exigem ao menos uma alegação por reply.
    if family.startswith('poison') or family == 'migration_ambiguous':
        replies = max(1, replies)
    config['arp_reply_count'] = replies
    return config


def replay(config):
    # Importação offline explícita, igual ao runner de testes do MVP.
    conf.route_autoload = False
    conf.route6_autoload = False
    with patch('scapy.interfaces.NetworkInterfaceDict.reload'):
        from scapy.all import ARP, IP, UDP, Ether, Raw, rdpcap
        from scapy.utils import PcapWriter
        from netsentinel.capture.config import CaptureConfig
        from netsentinel.capture.service import CaptureService
        from netsentinel.analysis.features import FeatureExtractor
    packets = []
    if not 0 <= config['arp_reply_count'] <= config['arp_count']:
        raise ValueError('Contagem de replies fora do total ARP.')
    # Intercalar opcodes distribui requests/replies durante a janela inteira.
    operations = [2] * config['arp_reply_count'] + [1] * (
        config['arp_count'] - config['arp_reply_count'])
    random.Random(config['arp_count'] * 1000 + config['arp_reply_count']).shuffle(operations)
    for index, operation in enumerate(operations):
        if operation == 2:
            packet = Ether(src=TARGET, dst=VICTIM)/ARP(
                op=2, hwsrc=TARGET, psrc='192.0.2.1', hwdst=VICTIM, pdst='192.0.2.2')
        else:
            # Request legítimo pelo MAC da vítima; anuncia o IP próprio do alvo.
            packet = Ether(src=TARGET, dst='ff:ff:ff:ff:ff:ff')/ARP(
                op=1, hwsrc=TARGET, psrc='192.0.2.3',
                hwdst='00:00:00:00:00:00', pdst='192.0.2.2')
        packet.time = 1700000000 + 0.01 + 7.9*index/config['arp_count']
        packets.append(packet)
    if config['gateway_claim']:
        packet = Ether(src=GATEWAY, dst=VICTIM)/ARP(
            op=2, hwsrc=GATEWAY, psrc='192.0.2.1', hwdst=VICTIM, pdst='192.0.2.2')
        packet.time = 1700000000 + 0.02
        packets.append(packet)
    for index in range(config['payload_count']):
        packet = Ether(src=TARGET, dst=VICTIM)/IP(src='192.0.2.3', dst='192.0.2.2')/UDP(
            sport=10000, dport=10001)/Raw(b'x'*config['payload_size'])
        packet.time = 1700000000 + 0.03 + 7.8*index/config['payload_count']
        packets.append(packet)
    buffer = io.BytesIO()
    writer = PcapWriter(buffer, linktype=1, sync=True)
    writer.write(sorted(packets, key=lambda p: p.time))
    content = buffer.getvalue()
    now = [0.0]
    snapshots = []
    service = CaptureService(CaptureConfig('offline', 8, 10000, True), snapshots.append,
                             clock=lambda: now[0])
    service.emit()  # fixa início em 0, independente do primeiro pacote
    for packet in rdpcap(io.BytesIO(content)):
        now[0] = float(packet.time)-1700000000
        service.ingest(packet)
    now[0] = 8.0
    service.emit()
    context = Context(Reputation(config['reputation']), config['baseline_bps'])
    inputs = FeatureExtractor(context, context).extract(snapshots[-1])[TARGET]
    return content, inputs


def generate(directory):
    directory = Path(directory)
    (directory/'pcaps').mkdir(parents=True, exist_ok=True)
    rng = random.Random(SEED)
    ratio_rng = random.Random(SEED + 1)
    records = []
    for family, label, count in FAMILIES:
        splits = ['train']*int(count*0.6) + ['validation']*int(count*0.2)
        splits += ['test']*(count-len(splits))
        rng.shuffle(splits)
        for index, split in enumerate(splits):
            identifier = f'{family}-{index:03d}'
            config = scenario(family, rng, ratio_rng)
            content, inputs = replay(config)
            (directory/'pcaps'/f'{identifier}.pcap').write_bytes(content)
            records.append({'id': identifier, 'family': family, 'label': label,
                            'split': split, 'config': config, 'inputs': asdict(inputs),
                            'pcap_sha256': hashlib.sha256(content).hexdigest()})
    (directory/'dataset.json').write_text(json.dumps(
        {'synthetic': True, 'dataset_version': DATASET_VERSION, 'seed': SEED,
         'ratio_seed': SEED + 1, 'window_seconds': 8, 'records': records},
        indent=2)+'\n')
    return records


def load(directory):
    manifest = json.loads((Path(directory)/'dataset.json').read_text())
    if manifest.get('dataset_version') != DATASET_VERSION:
        raise ValueError('Corpus invalidado: regenere a versão 2 com requests/replies reais.')
    records = manifest['records']
    if any('arp_reply_ratio' not in record['inputs'] for record in records):
        raise ValueError('Manifesto incompleto: ratio deve ser extraído do PCAP.')
    return records


def inputs_of(records):
    return [RiskInputs(**dict(item['inputs'], missing_reasons=tuple(
        item['inputs']['missing_reasons']))) for item in records]
